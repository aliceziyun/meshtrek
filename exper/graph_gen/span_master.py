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

	p_dist = subparsers.add_parser(
		"dist",
		help="Plot distribution of request overheads",
	)
	p_dist.add_argument(
		"-f",
		"--file",
		dest="file",
		required=True,
		help="Input file path",
	)
	p_dist.add_argument(
		"-l",
		"--len",
		dest="length",
		type=int,
		required=True,
		help="Length of the request"
	)
	p_dist.add_argument(
		"-t",
		"--type",
		dest="dist_type",
		choices=["filter", "wait", "parse", "overhead"],
		required=True,
		help="Type of distribution to plot",
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
		# dist(file=args.file, type=args.dist_type, length=args.length)
		print(f"[dist] file={args.file}")
		span_meta = read_span_meta_from_file(args.file)
		plotter = span_plotter.SpanPlotter()
		plotter.plot_dist_graph(span_meta=span_meta, dist_type=args.dist_type, length=args.length)
		return 0

	# Should be unreachable due to argparse choices
	parser.error(f"Unknown op: {args.op}")
	return 2

if __name__ == "__main__":
	# raise SystemExit(main())

	data_dir = "/Users/alicesong/Desktop/research/meshtrek/trace_synthetic_b16_http1"
	# 遍历data dir下的所有目录
	# import os
	# for dir_name in os.listdir(data_dir):
	# 	dir_path = os.path.join(data_dir, dir_name)
	# 	print(f"Checking dir: {dir_path}")
	# 	if os.path.isdir(dir_path):
	# 		# 以trace_res_branch1开头的dir，可以选择
	# 		if dir_name.startswith("trace_res_branch16"):
	# 			# 遍历dir下的所有文件
	# 			for file_name in os.listdir(dir_path):
	# 				# 以trace_output_service0开头的文件为entry file
	# 				if file_name.startswith("trace_output_service0"):
	# 					entry_file_path = os.path.join(dir_path, file_name)
	# 					print(f"Processing dir: {dir_path}, entry file: {entry_file_path}")
	# 					span_formatter.SpanFormatter(dir=dir_path, entry_file=entry_file_path).format_span_file()

	# 				# 结束后，把当前脚本目录下所有json文件，移动到当前遍历的dir下
	# 				current_dir = os.path.dirname(os.path.abspath(__file__))
	# 				for file in os.listdir(current_dir):
	# 					if file.endswith(".json"):
	# 						src_path = os.path.join(current_dir, file)
	# 						dst_path = os.path.join(dir_path, file)
	# 						os.rename(src_path, dst_path)
	# 						print(f"Moved {src_path} to {dst_path}")