#!/bin/zsh
# Duplo clique abre o painel. Deixe esta janela aberta enquanto usa.
cd "$(dirname "$0")"
(sleep 1 && open "http://localhost:4400") &
.venv/bin/python painel/servidor.py
