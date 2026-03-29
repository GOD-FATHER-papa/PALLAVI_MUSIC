# Copyright (c) 2026 Vibe-Bots
# Open-sourced under MIT terms.
# Included within AnonMusic framework.


class AssistantErr(Exception):
    def __init__(self, errr: str):
        super().__init__(errr)
