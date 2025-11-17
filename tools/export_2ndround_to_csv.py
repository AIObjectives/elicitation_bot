import csv
from io import StringIO
import firebase_admin
from firebase_admin import credentials, firestore
import os, json

def get_second_round_data(db, collection_name):
    """
    Extract ONLY the message texts inside:
        second_round_interactions: [ { message: "...", ... }, ... ]
    Skip everything else.
    Skip 'info' document.
    Return list of plain message strings.
    """
    try:
        collection_data = db.collection(collection_name).stream()
        messages = []

        for doc in collection_data:
            if doc.id == "info":
                continue

            doc_data = doc.to_dict()

            second_data = doc_data.get("second_round_interactions", [])
            if not second_data:
                continue

            for entry in second_data:
                if isinstance(entry, dict) and "message" in entry:
                    messages.append(entry["message"])
                else:
                    messages.append("")

        return messages

    except Exception as e:
        print(f"Error while extracting data from {collection_name}: {e}")
        return []


def generate_second_round_csv(messages):
    """
    Generate CSV containing ONLY:
    - ID  (row number)
    - comment  (message text)
    """
    if not messages:
        return ""

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(["ID", "comment"])

    # Write rows
    for idx, msg in enumerate(messages, start=1):
        writer.writerow([idx, msg])

    return output.getvalue()


def main():
    """
    Extract ONLY second-round comments and generate a very simple CSV:
    Columns: ID, comment
    """

    cred = credentials.Certificate('xxx.json')
    firebase_admin.initialize_app(cred)

    db = firestore.client()

    collection_names = [
        "xxx",
    ]

    for collection_name in collection_names:
        print(f"Extracting second-round data from: {collection_name}")

        messages = get_second_round_data(db, collection_name)
        csv_content = generate_second_round_csv(messages)

        filename = f"{collection_name}_second_round.csv"
        with open(filename, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)

        print(f"Saved: {filename}")


if __name__ == "__main__":
    main()
