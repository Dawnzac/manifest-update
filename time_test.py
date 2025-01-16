import re

text = "Update version: Headlamp.headlamp version 0.27.0"

# Use regex to extract the package name
match = re.search(r":\s([\w.]+)\sversion", text)
if match:
    package_name = match.group(1)
    print(package_name)
else:
    print("Package name not found")
