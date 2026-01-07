package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	ListenAddr     = "0.0.0.0:15001"
	SharedEnvoyDNS = "shared-envoy.mesh-proxy.svc.cluster.local:18080"

	// Linux netfilter original dst
	SO_ORIGINAL_DST = 80
)

func main() {
	log.SetFlags(log.LstdFlags | log.Lmicroseconds)

	ln, err := listenTransparent(ListenAddr)
	if err != nil {
		log.Fatalf("listenTransparent(%s): %v", ListenAddr, err)
	}
	log.Printf("node-forwarder listening (transparent) on %s, forwarding to %s", ListenAddr, SharedEnvoyDNS)

	for {
		c, err := ln.Accept()
		if err != nil {
			log.Printf("accept: %v", err)
			continue
		}
		go handleConn(c)
	}
}

// MUST: IP_TRANSPARENT on the listening socket so TPROXY-delivered packets are accepted.
func listenTransparent(addr string) (net.Listener, error) {
	lc := net.ListenConfig{
		Control: func(network, address string, c syscall.RawConn) error {
			var err error
			_ = c.Control(func(fd uintptr) {
				// Critical for TPROXY
				err = syscall.SetsockoptInt(int(fd), syscall.SOL_IP, syscall.IP_TRANSPARENT, 1)
				if err != nil {
					return
				}
				_ = syscall.SetsockoptInt(int(fd), syscall.SOL_SOCKET, syscall.SO_REUSEADDR, 1)
			})
			return err
		},
	}
	return lc.Listen(context.Background(), "tcp", addr)
}

func handleConn(c net.Conn) {
	defer c.Close()

	orig, _ := getOriginalDst(c)

	br := bufio.NewReader(c)
	req, err := http.ReadRequest(br)
	if err != nil {
		log.Printf("read request failed (orig=%s): %v", orig, err)
		return
	}

	// Ensure Host exists; usually already present for HTTP/1.1.
	if strings.TrimSpace(req.Host) == "" && strings.TrimSpace(orig) != "" {
		req.Host = orig
	}

	var out bytes.Buffer
	fmt.Fprintf(&out, "%s %s HTTP/1.1\r\n", req.Method, req.URL.RequestURI())

	// Write Host explicitly; avoid duplicates
	out.WriteString("Host: " + req.Host + "\r\n")
	req.Header.Del("Host")

	// Debug marker
	out.WriteString("x-node-forwarder: tproxy\r\n")

	// Copy remaining headers
	for k, vv := range req.Header {
		for _, v := range vv {
			out.WriteString(k + ": " + v + "\r\n")
		}
	}
	out.WriteString("\r\n")

	up, err := net.DialTimeout("tcp", SharedEnvoyDNS, 2*time.Second)
	if err != nil {
		log.Printf("dial shared envoy failed (orig=%s host=%s): %v", orig, req.Host, err)
		return
	}
	defer up.Close()

	// Send headers then stream body
	if _, err := up.Write(out.Bytes()); err != nil {
		log.Printf("write headers to shared envoy failed: %v", err)
		return
	}
	if req.Body != nil {
		_, _ = io.Copy(up, req.Body)
		_ = req.Body.Close()
	}

	// Stream response back
	_, _ = io.Copy(c, up)

	log.Printf("ok orig=%s host=%s %s %s", orig, req.Host, req.Method, req.URL.Path)
}

func getOriginalDst(c net.Conn) (string, error) {
	tcp, ok := c.(*net.TCPConn)
	if !ok {
		return "", errors.New("not TCPConn")
	}
	rawConn, err := tcp.SyscallConn()
	if err != nil {
		return "", err
	}

	var addr string
	var controlErr error
	controlErr = rawConn.Control(func(fd uintptr) {
		raw := make([]byte, 16)
		optlen := uint32(len(raw))
		_, _, e := syscall.Syscall6(syscall.SYS_GETSOCKOPT,
			fd,
			uintptr(syscall.SOL_IP),
			uintptr(SO_ORIGINAL_DST),
			uintptr(unsafe.Pointer(&raw[0])),
			uintptr(unsafe.Pointer(&optlen)),
			0,
		)
		if e != 0 {
			return
		}
		port := binary.BigEndian.Uint16(raw[2:4])
		ip := net.IPv4(raw[4], raw[5], raw[6], raw[7])
		addr = fmt.Sprintf("%s:%d", ip.String(), port)
	})
	if controlErr != nil {
		return "", controlErr
	}
	if addr == "" {
		return "", errors.New("SO_ORIGINAL_DST not available")
	}
	return addr, nil
}

