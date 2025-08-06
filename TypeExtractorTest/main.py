from pylya.hook_loader import install_hooks
from pylya.analysis import TypeExtractor

install_hooks(
    config_path="config.json",
    mode="learn",
    analyses=[TypeExtractor(outfile="type.log")]
)

import string_utils

result1 = string_utils.concat("hello", "world")
result2 = string_utils.shout("hello")
result3 = string_utils.count_chars("hello")

print(result1)
print(result2)
print(result3)