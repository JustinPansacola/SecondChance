from kafka import KafkaConsumer
from slack_bolt import App
import json

KAFKA_SERVER = 'localhost:9092'
TOPIC_NAME = 'slack'

def send_message_to_channel(message):

    app = App(token=message["token"])
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Hello your offer for item name: {message['itemName']} (Item ID: {message['itemId']}) is {message['message']}!"
            }
        },
        {
			"type": "image",
			"title": {
				"type": "plain_text",
				"text": "item image"
			},
                "block_id": "image4",
                "image_url": 'https://picsum.photos/id/237/200/300',
                "alt_text": "item image"
		}
    ]
    try:
        response = app.client.chat_postMessage(
            channel=message['channelId'],
            blocks=blocks
        )
        print("Message sent: ", message)
    except Exception as e:
        print("Error sending message: ", e)


consumer = KafkaConsumer(TOPIC_NAME, bootstrap_servers=KAFKA_SERVER, value_deserializer=lambda m: json.loads(m.decode('utf-8')))


for message in consumer:
    # channel_id = "C04SYABL19Q"  # Replace with your channel ID

    message_text = message.value
    send_message_to_channel(message_text)

