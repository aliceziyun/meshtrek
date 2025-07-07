import os
import argparse

# get line by keyword
def get_line_by_keyword(file, keyword):
    res_lines = []
    if not os.path.exists(file):
        print(f"File {file} does not exist")
        exit(1)
    
    with open(file, "r") as f:
        lines = f.readlines()
        for line in lines:
            if keyword in line:
                # remove all the blank spaces before the keyword
                line = line.split(keyword)[1].strip()
                # get the number part of the line
                if "ms" in line:
                    line = line.split("ms")[0]
                elif "s" in line:
                    line = float(line.split("s")[0]) * 1000
                res_lines.append(line)
    return res_lines

def generate_result(datas):
    res = []
    # group the data by 5, calculate the average
    for i in range(0, len(datas), 3):
        group = datas[i:i+3]
        avg = sum([float(x) for x in group]) / len(group)
        res.append(avg)
    return res

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get line by keyword")
    parser.add_argument(
        "-k", "--keyword", type=str, required=True, help="Keyword to search for"
    )
    parser.add_argument(
        "-f", "--file", type=str, required=True, help="File to search in"
    )

    args = parser.parse_args()
    keyword = args.keyword
    file = args.file

    print(generate_result(get_line_by_keyword(file, keyword)))
