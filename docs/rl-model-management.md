# Monthly RL model management (Issue 13)

The monthly selector has a separate local model artifact. Its metadata records model name and version, UTC training date, selected checkpoint steps, environment version, training seed, dataset version, complete evaluation evidence, and a SHA-256 checksum of the ZIP. The original 16-feature website selector retains its own artifact and existing process-level cache.

`app.rl.dynamic_model_management` provides four functions:

| Function | Behavior |
| --- | --- |
| `save_model(model, metadata, directory)` | Validates the policy shape and provenance, writes pending files, replaces the ZIP and JSON, and clears the in-process load cache. |
| `load_model(directory)` | Verifies versions and checksum, checks the 19-feature/63-action spaces, then reuses a loaded DQN for repeated calls with the same artifact digest. |
| `model_exists(directory)` | Reports whether versioned metadata and its matching ZIP are present; does not deserialize the policy. |
| `get_model_metadata(directory)` | Returns verified JSON provenance and evidence without importing PyTorch. |

The offline training command now calls `save_model()` after choosing its best validation checkpoint. The committed model's training date is **2026-09-30 UTC**, when the Issue 12 run took place; adding management metadata did not retrain or change its model ZIP or held-out test result.

To inspect the committed artifact from the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.rl.dynamic_model_management
..\.venv\Scripts\python -m pytest tests\test_dynamic_model_management.py tests\test_dynamic_training.py -q
```

The inspection command checks the checksum and prints name, version, training date/steps, environment, seed, dataset, and checksum. It fails if the artifact is missing or incompatible. There is no new website screen or account-data inference path in this issue; the signed-in Research page still uses the older snapshot policy.
