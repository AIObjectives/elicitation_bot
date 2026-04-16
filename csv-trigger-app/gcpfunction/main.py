import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO
import csv

import functions_framework
from google.cloud import storage
from firebase_admin import credentials, firestore, initialize_app, get_app

import config


def get_all_user_inputs(db, event_id):
    """ Fetch all user messages (excluding bot responses) from the event's participants subcollection """
    try:
        collection_data = db.collection('elicitation_bot_events').document(event_id).collection('participants').stream()
        all_messages = {}

        for doc in collection_data:
            doc_data = doc.to_dict()
            participant_id = doc.id

            user_messages = [
                interaction.get('message', '') for interaction in doc_data.get('interactions', [])
                if isinstance(interaction, dict) and 'message' in interaction and 'response' not in interaction
            ]

            cleaned_messages = " ".join(user_messages).replace('[', '').replace(']', '').replace("'", "")

            name = doc_data.get('name', '')
            other_fields = {key: value for key, value in doc_data.items()
                            if key not in ['interactions', 'second_round_interactions', 'name',
                                           'participant_id', 'event_id']}

            all_messages[participant_id] = {
                'name': name,
                'comment-body': cleaned_messages,
                **other_fields
            }
        return all_messages
    except Exception as e:
        print(f"An error occurred: {e}")


def generate_dynamic_csv(all_messages):
    """ Generate CSV content dynamically from all fields in user messages """
    output = StringIO()
    all_keys = set()

    for participant_id, doc_data in all_messages.items():
        all_keys.update(doc_data.keys())

    writer = csv.writer(output)
    headers = ['comment-id'] + sorted(all_keys)
    writer.writerow(headers)

    index = 1
    for participant_id, doc_data in all_messages.items():
        row = [index]
        row += [doc_data.get(key, '') for key in sorted(all_keys)]
        writer.writerow(row)
        index += 1

    return output.getvalue()


def construct_email_body_html(csv_urls):
    email_body = """
    <html>
        <head>
            <style>
                body {
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    margin: 0; padding: 0;
                    background-color: #f0f3f5;
                    color: #1c1e21;
                }
                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                }
                .header {
                    text-align: center;
                    padding-bottom: 30px;
                    border-bottom: 1px solid #e6e6e6;
                }
                .header img {
                    max-width: 120px;
                    margin-bottom: 20px;
                }
                h1 {
                    font-size: 26px;
                    color: #1c1e21;
                    margin-bottom: 20px;
                }
                p {
                    font-size: 16px;
                    line-height: 1.6;
                    color: #4a4a4a;
                }
                .button {
                    display: inline-block;
                    padding: 12px 24px;
                    margin: 20px 0;
                    font-size: 16px;
                    color: #ffffff;
                    background-color: #007BFF;
                    text-decoration: none;
                    border-radius: 5px;
                    transition: background-color 0.3s ease;
                }
                .button:hover {
                    background-color: #0056b3;
                }
                .collection {
                    text-align: center;
                    margin: 30px 0;
                }
                .footer {
                    margin-top: 50px;
                    padding-top: 20px;
                    border-top: 1px solid #e6e6e6;
                    text-align: center;
                    font-size: 14px;
                    color: #999999;
                }
                .useful-links a {
                    text-decoration: none;
                    color: #007BFF;
                    font-size: 16px;
                    margin: 0 10px;
                }
                .unsubscribe {
                    color: #999999;
                    text-decoration: none;
                    font-size: 12px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <img src="https://aoiaiwhatsappdata2.s3.amazonaws.com/AOIlogo.jpg" alt="Company Logo">
                    <h1>Your Requested Data Collections</h1>
                </div>
                <p>Dear Valued Partner,</p>
                <p>We are pleased to provide you with the data collections you requested. Please use the buttons below to download each dataset individually:</p>
    """

    for collection_name, url in csv_urls.items():
        email_body += f"""
                <div class="collection">
                    <h2>{collection_name}.csv</h2>
                    <a href="{url}" class="button">Download {collection_name}</a>
                </div>
        """

    email_body += """
                <p>If you have any questions or need further assistance, please do not hesitate to reach out to our support team.</p>
                <div class="footer">
                    <div class="useful-links">
                        <a href="https://ai.objectives.institute/whitepaper">Whitepaper</a> |
                        <a href="https://www.wired.com/story/peter-eckersley-ai-objectives-institute/">AOI Legacy</a> |
                        <a href="https://ai.objectives.institute/projects">Programs</a>
                    </div>
                    <p>&copy; 2024 AOI Emre Turan. All rights reserved.</p>
                    <a href="#" class="unsubscribe">Unsubscribe</a>
                </div>
            </div>
        </body>
    </html>
    """

    return email_body


@functions_framework.http
def csv_handler(request):
    try:
        app = get_app()
    except ValueError:
        cred = credentials.Certificate(config.FIREBASE_CREDENTIALS)
        app = initialize_app(cred)

    db = firestore.client(app=app)

    email_recipient = request.args.get('email')
    collections_param = request.args.get('collections', '')
    collection_names = [name.strip() for name in collections_param.split(',') if name.strip()]

    if not email_recipient or not collection_names:
        return ('Email and collections parameters are required', 400)

    storage_client = storage.Client()
    bucket_name = config.GCS_BUCKET_NAME
    csv_urls = {}

    for collection_name in collection_names:
        all_messages = get_all_user_inputs(db, collection_name)
        csv_content = generate_dynamic_csv(all_messages)

        file_key = f'{collection_name}_user_messages.csv'
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_key)
        blob.upload_from_string(csv_content, content_type='text/csv')

        url = blob.generate_signed_url(
            expiration=datetime.timedelta(hours=1),
            method='GET',
            version='v4'
        )
        csv_urls[collection_name] = url

    email_body = construct_email_body_html(csv_urls)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Your Requested Data Collections'
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = email_recipient
    msg.attach(MIMEText(email_body, 'html'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(config.EMAIL_SENDER, config.GMAIL_APP_PASSWORD)
        smtp.sendmail(config.EMAIL_SENDER, email_recipient, msg.as_string())

    return ('Data processed and email sent successfully', 200)
