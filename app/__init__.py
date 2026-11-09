"""GeekCubo application package."""

import os

# LiteLLM fetches its model cost map from the network at import time unless it
# is told to use the copy bundled with the installed version. GeekCubo must
# start and serve without any outbound catalog call, so default to the bundled
# map. This runs before anything imports litellm; an operator can still
# override it in the environment.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
