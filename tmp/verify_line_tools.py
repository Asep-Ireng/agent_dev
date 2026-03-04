import sys
import os

# Add backend to path to import agent_tools
sys.path.append(os.path.abspath('r:/Kuliah/Kuliah Rui/Project Gabut/agent_dev/backend'))
from agent_tools import EditFileLinesTool, InsertAtLineTool

workspace = os.path.abspath('r:/Kuliah/Kuliah Rui/Project Gabut/agent_dev/workspace')
os.makedirs(workspace, exist_ok=True)
test_file = os.path.join(workspace, 'test_precision.txt')

# Create initial file
content = """Line 1
Line 2
Line 3
Line 4
Line 5
"""
with open(test_file, 'w') as f:
    f.write(content)

print(f"Created {test_file} with initial content.")

# 1. Test EditFileLines (Replace lines 2-4)
edit_tool = EditFileLinesTool(workspace_path=workspace)
result = edit_tool._run('test_precision.txt', 2, 4, "New Line 2\nNew Line 3\n")
print(f"Edit result: {result}")

with open(test_file, 'r') as f:
    print("Content after edit:")
    print(f.read())

# 2. Test InsertAtLine (Insert before line 2)
insert_tool = InsertAtLineTool(workspace_path=workspace)
result = insert_tool._run('test_precision.txt', 2, "Inserted Line\n")
print(f"Insert result: {result}")

with open(test_file, 'r') as f:
    print("Content after insert:")
    print(f.read())
