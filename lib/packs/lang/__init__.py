"""Language packs. Each pack exposes `SPECIALISTS: tuple[Specialist, ...]` (and may add a
`TOOLS` fragment). `_base` provides the registry machinery and the shared lanes; a profile
names the packs it wants and the registry is assembled from them.
"""
