# England vs Norway: Match Analysis

Tactical analysis and Python visualisations for England's 2-1 quarter-final win over Norway, developed as part of **Sports Data Campus - The World Cup of Data**.

The analysis examines how territorial control, pressure and chance creation changed across the match, with particular attention to England's decisive attacking windows and Jude Bellingham's two goals.

## Visuals

### Match Momentum

**Script:** `scripts/build_match_momentum.py`  
**Source:** `data/events.json`

A custom rolling five-minute attacking-threat index. England's net threat appears above the baseline and Norway's below it. Goal annotations and break markers provide match context.

The index combines positive On-Ball Value (OBV), shots, expected goals, goals, entries into dangerous areas and selected attacking or recovery actions. Contributions receive time-decay weighting and the plotted curve is smoothed.

The weights are hand-selected for this analysis. This is an exploratory editorial index, not an official metric or a reproduction of the Bundesliga/AWS momentum formula. Its values are index points, not probabilities or xG. Because goals receive an explicit bonus, goal-related peaks partly reflect that design choice and should not independently be interpreted as evidence of sustained build-up dominance.

The event weights and timing logic are documented in the script. Match periods and stoppage-time labels require particular care when adapting the chart to another match.

### Influence Profiles

**Script:** `scripts/build_influence_profiles.py`  
**Source:** `data/player_match_stats.json`

Six selected players illustrate the article's main themes:

- **England:** Jude Bellingham, Elliot Anderson and John Stones.
- **Norway:** Sander Berge, Martin Odegaard and Erling Haaland.

Each profile combines a headline statistic with supporting match totals and a short tactical interpretation. The selection is editorial, rather than an overall player ranking. Pass pairs use **completed/attempted** order.

## Project Structure

```text
fonts/                 Fonts required by the chart scripts
flags/                 Team flags and goal-marker assets
player_headshots/      Player portrait assets
scripts/               Analysis and rendering scripts
output/
  visuals/             Exported graphics
requirements.txt       Python dependencies
```

Some inputs and assets may need to be supplied separately, depending on redistribution permissions.

## Run Locally

Use Python 3.10 or newer. From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/build_match_momentum.py
python scripts/build_influence_profiles.py
```

## Data and Interpretation


- `events.json` supplies the momentum chart's event-level inputs and goal annotations.
- `player_match_stats.json` supplies the player-profile statistics.


## Data and Asset Permissions

data, player photographs, flags and fonts retain their respective ownership and licensing conditions. Check the applicable Sports Data Campus project agreement before publicly redistributing raw JSON/CSV files or other supplied materials. Their presence in a local project does not establish permission to publish them.

No third-party data or asset licence is granted by this README.

## Credits

**Analysis team:** Regina Khalil, Ulrich Haarmann, Imrane Talay and Jairo Rodriguez.

Developed as part of **Sports Data Campus - The World Cup of Data**.

Python implementation and visual iteration were developed with assistance from **OpenAI Codex**, with analytical direction and review by the project team.
