"""`appengine_config` gets loaded when starting a new application instance."""
import sys
import os.path
# add `lib` subdirectory to `sys.path`, so our `main` module can load
# third-party libraries.

sys.path.insert(0, 'google-api-python-client-gae-1.2.zip')
sys.path.insert(0, 'lib')
