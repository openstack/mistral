#!/usr/bin/env python

import sys


try:
    wf_name = str(sys.argv[1])
    branch_cnt = int(sys.argv[2])
    branch_depth = int(sys.argv[3])

    add_join = len(sys.argv) > 4
except:
    raise ValueError(
        'Usage: <script_name> workflow_name'
        ' number_of_parallel_branches branch_depth add_join'
    )


f = open('%s.mist' % wf_name, 'w')

# Writing a workflow header to the file.

f.write('---\n')
f.write("version: '2.0'\n\n")

f.write("%s:\n" % wf_name)
f.write("  tasks:\n")

# 1. First starting task.

f.write("    task_1:\n")
f.write("      action: std.noop\n")
f.write("      on-success:\n")

for branch_num in range(1, branch_cnt + 1):
    f.write("        - task_%s_1\n" % branch_num)

# 2. Branch tasks.

for branch_num in range(1, branch_cnt + 1):
    for task_num in range(1, branch_depth + 1):
        f.write("    task_%s_%s:\n" % (branch_num, task_num))
        f.write("      action: std.noop\n")

        if task_num < branch_depth:
            f.write("      on-success: task_%s_%s\n" % (branch_num, task_num + 1))
        elif add_join:
            f.write("      on-success: task_join\n")

# 3. The last "join" task, if needed.

if add_join:
    f.write("    task_join:\n")
    f.write("      join: all")

f.close()

print("Workflow '%s' is created." % wf_name)
