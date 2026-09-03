"""
Evaluate the chatbot intent classifier on a labeled test dataset.

Reports accuracy, per-class precision/recall/F1, macro averages,
and a confusion matrix.

Usage:
    python evaluate.py
    python evaluate.py --dataset data/intent_test.json
"""
import argparse
import json
from collections import Counter

from chatbot import Chatbot, load_intents

UNKNOWN_LABEL = "unknown"  # dataset's label for "no intent should match"


def load_dataset(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def run_predictions(bot, examples):
    """Return a list of (expected, predicted) tag pairs."""
    pairs = []
    for example in examples:
        predicted_tag, _confidence = bot.classify(example["query"])
        pairs.append((example["expected_intent"], predicted_tag or UNKNOWN_LABEL))
    return pairs


def compute_metrics(pairs, labels):
    true_positives = Counter()
    false_positives = Counter()
    false_negatives = Counter()
    confusion = {label: Counter() for label in labels}
    correct = 0

    for expected, predicted in pairs:
        confusion[expected][predicted] += 1
        if expected == predicted:
            correct += 1
            true_positives[expected] += 1
        else:
            false_positives[predicted] += 1
            false_negatives[expected] += 1

    accuracy = correct / len(pairs) if pairs else 0.0

    precision, recall, f1 = {}, {}, {}
    for label in labels:
        tp, fp, fn = true_positives[label], false_positives[label], false_negatives[label]
        precision[label] = tp / (tp + fp) if (tp + fp) else 0.0
        recall[label] = tp / (tp + fn) if (tp + fn) else 0.0
        denom = precision[label] + recall[label]
        f1[label] = (2 * precision[label] * recall[label] / denom) if denom else 0.0

    # Macro average gives each intent equal weight.
    macro_precision = sum(precision.values()) / len(labels)
    macro_recall = sum(recall.values()) / len(labels)
    macro_f1 = sum(f1.values()) / len(labels)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "macro_precision": macro_precision,
        "macro_recall": macro_recall,
        "macro_f1": macro_f1,
        "confusion": confusion,
    }


def print_report(metrics, labels, total):
    print(f"Evaluated {total} examples\n")
    print(f"Accuracy: {metrics['accuracy']:.3f}")
    print(f"Macro precision: {metrics['macro_precision']:.3f}")
    print(f"Macro recall:    {metrics['macro_recall']:.3f}")
    print(f"Macro F1:        {metrics['macro_f1']:.3f}\n")

    print(f"{'intent':<16}{'precision':>10}{'recall':>10}{'f1':>10}")
    for label in labels:
        print(
            f"{label:<16}{metrics['precision'][label]:>10.2f}"
            f"{metrics['recall'][label]:>10.2f}{metrics['f1'][label]:>10.2f}"
        )

    print("\nConfusion matrix (rows = expected, columns = predicted)")
    header = "expected \\ predicted".ljust(20) + "".join(f"{label[:8]:>9}" for label in labels)
    print(header)
    for true_label in labels:
        row = metrics["confusion"][true_label]
        counts = "".join(f"{row[pred_label]:>9}" for pred_label in labels)
        print(f"{true_label:<20}{counts}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="data/intent_test.json")
    parser.add_argument("--intents-file", default="intents.json")
    args = parser.parse_args()

    intents = load_intents(args.intents_file)
    bot = Chatbot(intents=intents)
    examples = load_dataset(args.dataset)

    labels = sorted({intent["tag"] for intent in intents} | {UNKNOWN_LABEL})
    pairs = run_predictions(bot, examples)
    metrics = compute_metrics(pairs, labels)
    print_report(metrics, labels, len(examples))


if __name__ == "__main__":
    main()
