# Copyright 2019 - Nokia Networks
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""
"""

import sys


def _print_help():
    print("\nUsage: <script_name> <input_file_name> <output_file_name>\n")
    print(
        'The script processes a Mistral profiler log file (<input_file_name)\n'
        'and generates a report into a file (<output_file_name>) that\n'
        'contains statistics about each profiler trace: \n'
        '-------------------------------------------------------------\n'
        ' Total time | Max time | Avg time | Occurrences | Trace name \n'
        '-------------------------------------------------------------\n'
        ' ...          ...        ...        ...           ...\n'
    )


def main():
    try:
        in_file_name = str(sys.argv[1])
        out_file_name = str(sys.argv[2])
    except:
        _print_help()

        return "Failed to parse arguments."

    print('Ranking profiled methods...')

    in_f = open(in_file_name, 'r')
    out_f = open(out_file_name, 'w')

    # {trace_name: [total_time, max_time, occurrences]}
    d = dict()

    with in_f:
        for line in in_f:
            tokens = line.split()

            # Skip all "-start" lines that don't contain a duration in seconds.
            # Processing only "-stop" lines.
            if len(tokens[1]) > 10:
                continue

            trace_name = tokens[5]
            trace_name = trace_name[0:len(trace_name) - 5]

            duration = float(tokens[1])

            if trace_name not in d:
                d[trace_name] = [duration, duration, 1]
            else:
                l = d[trace_name]

                l[0] = l[0] + duration
                l[2] = l[2] + 1

                if duration > l[1]:
                    l[1] = duration

    result = sorted(d.items(), key=lambda x: x[1][0], reverse=True)

    out_f.write('Total time | Max time | Avg time | Occurrences | Trace name\n')
    out_f.write('-' * 90)
    out_f.write('-\n')

    for item in result:
        out_f.write(
            '{0:<12.3f} {1:<10.3f} {2:<10.3f} {3:<13d} {4}\n'.format(
                item[1][0],
                item[1][1],
                item[1][0] / item[1][2],
                item[1][2],
                item[0]
            )
        )

    out_f.close()

    print("Ranking file was successfully created: %s" % out_file_name)


if __name__ == '__main__':
    sys.exit(main())
