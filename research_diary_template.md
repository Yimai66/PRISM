# PRISM Role 1 Research Diary

## Week 7

## Aim
This week I focused on building the technical prototype of PRISM. My goal was to create a working web demo that follows the pipeline: user question → translation → multilingual search → disagreement detection.

## What I tried
- Built the Streamlit interface with an input box, language selector, and search button.
- Integrated the Role 2 taxonomy into the LLM prompt.
- Added side-by-side result display so the app does not collapse multiple language frames into one answer.
- Added a mock mode so the interface can be tested even before API keys are working.

## What worked
- The basic interface successfully displays different language panels side by side.
- The six-type disagreement taxonomy can be inserted directly into the LLM prompt.
- The app can export a CSV-style record useful for Role 4 evaluation.

## What did not work / problems encountered
- Live search results are unstable and can change across time.
- Translation can change the meaning of the search query slightly.
- Type F omission is difficult to detect because a source can be silent about something without directly contradicting another source.
- API keys and rate limits may affect whether the live demo works smoothly.

## Decisions made
- I chose Streamlit because it allows a working prototype to be built quickly without a separate front-end and back-end.
- I chose a side-by-side UI because Role 2's case analysis warns against synthesizing multiple language results into one combined answer.
- I treated the LLM output as a classification suggestion, not as a final answer.

## Next steps
- Test the prototype with the six Role 2 demo questions.
- Save outputs for Role 4's evaluation.
- Improve error messages and loading states.
- Deploy the demo online if API keys are stable.

## Questions for the lecturer / team
- How much accuracy is expected from the automatic disagreement detector?
- Should the final demo prioritize Wikipedia-style cases or live open web search?
- How should we evaluate Type F omission when silence is difficult to measure computationally?
