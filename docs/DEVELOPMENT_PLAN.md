# DK-Picks-Optimizer — Development Plan

**Priority:** 1 (Flagship — do this first)  
**Current state:** ~70% done · ~65/100  
**Target score:** 91/100  
**Timeline:** ~3 weeks

## Goal

Transform this ML sports betting optimizer from a working prototype into a production-grade, interview-proof portfolio flagship. Every change must be testable, explainable, and demonstrable in a live interview.

## What Exists (do not rebuild, only improve)

- LightGBM leg model with isotonic calibration
- Kelly criterion + portfolio optimizer
- Walk-forward backtester
- FastAPI endpoints
- Streamlit dashboard

## Task Checklist

- [ ] **TASK 1:** CI/CD Pipeline (GitHub Actions) — pytest + ruff, 75% coverage floor, CI badge
- [ ] **TASK 2:** Backtest Results section in README (8+ weeks, baselines, metric explanations)
- [ ] **TASK 3:** Architecture diagram in README (mermaid)
- [ ] **TASK 4:** Calibration plot script → `docs/calibration_plot.png`
- [ ] **TASK 5:** Streamlit Community Cloud deploy + live demo badge
- [ ] **TASK 6:** Repo description + professional ML framing (non-gambling language)
- [ ] **TASK 7:** Tests — leakage, ECE, Kelly cap, API schema
- [ ] **TASK 8:** `docs/INTERVIEW.md` with 6 Q&As

## Rules

- Run pytest after EVERY task. Do not move to next task if tests fail.
- No magic numbers — everything configurable in `config.yaml`
- Every function must have a docstring
- README must be updated as you go, not at the end
- Do NOT add new ML models — improve what exists

## Cursor Prompt

Paste the contents of [`docs/CURSOR_PROMPT.md`](./CURSOR_PROMPT.md) into Cursor when starting a session on this project.
