# Known issues

The freeze cleanup inventory found no outstanding `TODO` or `FIXME` markers in
the tracked backend or frontend source. It also found no frontend
`console.log()` calls. Intentional progress and report output in the scripts
under `backend/scripts/` is retained because those scripts are command-line
tools rather than application debug output.
