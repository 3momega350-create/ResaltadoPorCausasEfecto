from main import setup_causal_matcher, nlp, analyze_text

def run_test():
    text = (
        "The mission failed because the engine overheated. "
        "If you heat water, it boils. "
        "The storm led to power outages. Therefore, many flights were canceled."
    )
    matcher = setup_causal_matcher(nlp)
    highlights = analyze_text(text, matcher)
    print('Highlights:', highlights)

if __name__ == '__main__':
    run_test()
