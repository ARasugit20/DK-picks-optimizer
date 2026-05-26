from betting_system.optimizer.parlay_builder import build_parlay_candidates


def test_parlay_builder_filters_duplicate_player():
    legs = [
        {"game_id": "g1", "market_type": "player_points_over", "player_id": "p1", "line": 20.5, "odds_american": -110, "p_hit": 0.6, "edge": 0.05, "ev_per_unit": 0.02},
        {"game_id": "g1", "market_type": "player_rebounds_over", "player_id": "p1", "line": 8.5, "odds_american": -110, "p_hit": 0.6, "edge": 0.05, "ev_per_unit": 0.02},
        {"game_id": "g2", "market_type": "player_assists_over", "player_id": "p2", "line": 5.5, "odds_american": -110, "p_hit": 0.6, "edge": 0.05, "ev_per_unit": 0.02},
    ]
    cands = build_parlay_candidates(legs, corr_path=None)
    # Any candidate including both p1 legs should be filtered out
    for c in cands:
        players = [l["player_id"] for l in c["legs"]]
        assert len(players) == len(set(players))

