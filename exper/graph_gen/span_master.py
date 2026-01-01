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

def _build_parser():
	parser = argparse.ArgumentParser(
		prog="span_master",
		description="Span processing tool (clean/gen).",
	)

	subparsers = parser.add_subparsers(
		dest="op",
		required=True,
		metavar="{clean,gen}",
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

	return parser


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
		print(f"[gen] file={args.file} request_id={args.request_id}")
		return 0

	# Should be unreachable due to argparse choices
	parser.error(f"Unknown op: {args.op}")
	return 2

if __name__ == "__main__":
	raise SystemExit(main())