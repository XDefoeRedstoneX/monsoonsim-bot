# Manual Verification Checklist

The unit tests cover the pure logic (order maths, parsing, config). The pieces
that can only be checked against a **live MonsoonSim session** are listed here —
the DOM selectors and end-to-end flows. Work through this after any change that
touches `driver.py` or `selectors.py`.

> Tip: keep the GUI **Log** panel visible — every step reports there. If a step
> fails, copy the red error line; it names the selector that didn't match.

## Setup
- [ ] Chrome started with `--remote-debugging-port=9222`
- [ ] Logged in to MonsoonSim with an active simulation open
- [ ] `python -m monsoon_bot` launches the GUI without errors

## Connection & diagnostics
- [ ] **Connect to Browser** → status turns green, log shows the MonsoonSim URL
- [ ] **Run Self-Test** → all three checks pass (Page URL, Read day KPI, Retail panel)
- [ ] Disconnect case: with no MonsoonSim tab open, Connect shows a clear error

## Global settings
- [ ] Switching **Product Set** updates the priority checkboxes and calc labels
- [ ] Switching **Location Set** clears the location dropdown

## Retail AI
- [ ] **Fetch Locations** lists your owned retail stores
- [ ] **Calculate Order** (dry run) shows per-product quantities and places no order
- [ ] Numbers look sane vs. the in-game space/stock (spot-check one product)
- [ ] Ticking a priority product shifts more volume toward it on recalculation
- [ ] **Run One-Time Replenish** actually submits the order in-game
- [ ] Order respects the selected **Target Fill Level**
- [ ] A near-full store returns "No order needed"

## Presets
- [ ] Tick priorities for a location, restart the app → they are remembered
- [ ] Different product sets keep separate presets for the same location

## Service / HR
- [ ] **Auto-Handle First Service Request** opens a request and assigns mandays
- [ ] With no pending requests, it reports "No new service requests found"

## Automation loops
- [ ] **Start Retail Loop** processes every fetched location, then waits for the next day
- [ ] **Start Service Loop** handles requests each day
- [ ] **Start Full Automation** does both
- [ ] **Stop** cleanly halts a running loop (status returns to IDLE)
- [ ] Loop ends gracefully on the final in-game day ("GAME OVER")

## Resilience
- [ ] Rapid actions that trigger "Slow down, you click too fast" are retried, not fatal
- [ ] Closing the window cancels running loops and disconnects cleanly
