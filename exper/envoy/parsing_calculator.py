# this file is use to calculate the result of hook
# and will only calculate the time spent on http header parsing

pending_entries = {}

def read_file(file_path):
    with open(file_path, 'r') as file:
        content = file.readlines()
    return content


def parse_time_entry(time_entry):
    """
    Break down a time entry like: "Connection ID: 7, Elapsed Time: 117669 ns"
    into a dictionary with keys 'connection_id' and value 'elapsed_time'.
    """
    parts = time_entry.split(',')
    connection_id = int(parts[0].split(':')[1].strip())
    elapsed_time = int(parts[1].split(':')[1].strip().replace('ns', ''))
    pending_entries[connection_id] = elapsed_time