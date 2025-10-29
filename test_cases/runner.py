from Cerbex.hook_loader import install_hooks

# Load hooks in 'learn' mode: this writes dependencies.json, events.json, allowlist.json.
install_hooks(
    config_path='config.json',
    analyses=[],
    mode='enforce',
    allowlist_path="allowlist.json"
)
# Run the target instrumented script
import request_example
request_example.main()
