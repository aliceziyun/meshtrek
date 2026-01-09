"""Span tool master entry.
- clean: clean trace/span files format
	-e / --entry-file: entry file
	-d / --dir:        directory containing files

- gen: generate span graph for a given file and request id
	-f / --file:       input file
	-id / --request-id: request id
"""

import argparse
import span_formatter
import span_plotter
import json

def _build_parser():
	parser = argparse.ArgumentParser(
		prog="span_master",
		description="Span processing tool (clean/gen).",
	)

	subparsers = parser.add_subparsers(
		dest="op",
		required=True,
		metavar="{clean,gen,topk,dist}",
		help="Operation to perform",
	)

	# op = clean
	p_clean = subparsers.add_parser(
		"clean",
		help="Clean trace/span output",
	)
	p_clean.add_argument(
		"-e",
		"--entry-file",
		dest="entry_file",
		required=True,
		help="Entry file path",
	)
	p_clean.add_argument(
		"-d",
		"--dir",
		dest="file_dir",
		required=True,
		help="Directory containing files",
	)

	# op = gen
	p_gen = subparsers.add_parser(
		"gen",
		help="Generate outputs for a given request id",
	)
	p_gen.add_argument(
		"-f",
		"--file",
		dest="file",
		required=True,
		help="Input file path",
	)
	p_gen.add_argument(
		"-id",
		"--request-id",
		dest="request_id",
		required=True,
		help="Request id to filter",
	)

	# op = topk
	p_topk = subparsers.add_parser(
		"topk",
		help="Get top K requests by overhead time",
	)
	p_topk.add_argument(
		"-f",
		"--file",
		dest="file",
		required=True,
		help="Input file path",
	)
	p_topk.add_argument(
		"-k",
		"--k",
		dest="k",
		type=int,
		required=True,
		help="Top K requests to retrieve",
	)
	p_topk.add_argument(
		"-l",
		"--len",
		dest="length",
		type=int,
		required=True,
		help="Length of the request"
	)

	return parser

def read_span_meta_from_file(file):
	with open(file, 'r') as f:
		data = json.load(f)
	return data

def get_top_k(file, k, length):
	span_meta = read_span_meta_from_file(file)

	# filter by request length
	span_meta = [(request_id, meta) for request_id, meta in span_meta.items() if meta.get("total_sub_requests", 0) == length]
	
	# sorted by overhead time
	sorted_requests = sorted(
		span_meta,
		key=lambda item: item[1].get("overhead", 0),
		reverse=True
	)

	top_k_requests = sorted_requests[:k]
	return top_k_requests

def main(argv=None):
	parser = _build_parser()
	args = parser.parse_args(argv)

	# TODO: wire real implementations here
	if args.op == "clean":
		# clean(entry_file=args.entry_file, file_dir=args.file_dir)
		print(f"[clean] entry_file={args.entry_file} dir={args.file_dir}")
		span_formatter.SpanFormatter(dir=args.file_dir, entry_file=args.entry_file).format_span_file()
		return 0
	if args.op == "gen":
		# gen(file=args.file, request_id=args.request_id)
		plotter = span_plotter.SpanPlotter()
		spans = plotter.read_data(file_path=args.file, request_id=args.request_id)
		plotter.plot_span(spans)
		return 0
	if args.op == "topk":
		# top_k(file=args.file, k=args.k, length=args.length)
		top_k_requests = get_top_k(file=args.file, k=args.k, length=args.length)
		for request_id, meta in top_k_requests:
			print(f"Request ID: {request_id}, Overhead: {meta.get('overhead', 0)}, Request Time: {meta.get('request_time', 0)}")
		return 0
	if args.op == "dist":
		# dist(file=args.file)
		print(f"[dist] file={args.file}")
		span_meta = read_span_meta_from_file(args.file)
		

	# Should be unreachable due to argparse choices
	parser.error(f"Unknown op: {args.op}")
	return 2

if __name__ == "__main__":
	raise SystemExit(main())