from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

import os, sys

import requests
from invokes import invoke_http

import amqp_setup
import pika
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

department_url = 'http://localhost:5004/department'
carbon_calculator_url = 'http://localhost:5005/carbon_calc'
create_item_url = 'http://localhost:5006/create'
item_url = 'http://localhost:5007/item'
slack_url = 'http://localhost:5008/slack'

# data recieved from front end's accept button
# “id”: ObjectId,
# “itemName”: String,
# “creatorId”: ObjectId(User)
# "itemCategory": String,
# "isListed": Boolean,
    # Listing (“isListed” = True)
    # "itemPicture": BLOB,
    # "itemDescription": Null, String,
    # “Status”: String
    # "carbonEmission”: Null, Number,
    # “receivorId”: Null, ObjectId(User),


@app.route("/accept_item", methods=['POST'])
@cross_origin()
def accept_item():
    if request.is_json:
        try:
            # result = process_accept_item(request.json)
            result = test_slack(request.json)
            return result

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = f"{str(e)} at {str(exc_type)}: {fname}: line {str(exc_tb.tb_lineno)}"
            print(ex_str) 

            return jsonify ({
                "code": 500,
                "message": f"accept_item.py internal error: {ex_str}"
            })

#to test slack bot
def test_slack(item):
        #slack notification
        slack_result = invoke_http(
                f"{slack_url}",
                method="POST",
                json=item
            )
        # slack error
        code = slack_result['code']
        slack_data = slack_result['data']
        
        if code not in range(200, 300):
            print('\n\n-----Publishing the (slack error) message with routing_key=slack.error-----')
                
            message = {
                "code": 400,
                "message_type": "business_error",
                "data": "Invalid department ID"
            }
            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='slack.error', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("\nSlack error - Code {} - published to the RabbitMQ Exchange:".format(code))
            return slack_result
        
        else:
            message = {
                "code": 201,
                    "message_type": 'slack_notification',
                    "data": slack_data
            }
            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='slack.notify', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("------------ SLACK NOTIFICATION SENT SUCCESSFULLY - {} ------------".format(slack_data))
            return slack_result
        


def process_accept_item(item):
    item_id = item['id']
    buyerId = item["recievorId"]
    sellerId = item["recievorId"]

    #---------------------------------------------------------------------------------
    #change status of isListing from true to false
    if item["isListing"] == True:
        item_status = {
            "id": item_id,
            "isListing": False
        }
        new_item_result = invoke_http(
            f"{item_url}",
            method="PUT",
            json=item_status,
        )   

        print('\n\n-----Publishing the item accept notification message with routing_key=accept.notify-----')        

        
        message = {
            "code": 201,
            "message_type": "accept_notification",
            "data": new_item_result
        }

        message = json.dumps(message)

        amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key="accept.notify", 
        body=message, properties=pika.BasicProperties(delivery_mode = 2)) 
    
        print("\nItem accept notification published to RabbitMQ Exchange.\n")


    #---------------------------------------------------------------------------------
    # change ownership of item
        department_update_result = invoke_http(
            f"{department_url}/edit/{item['creatorId']}",
            method='PUT',
            json=item
        )
        code = department_update_result['code']

        # ownership of department not updated
        if code not in range(200,300):
            print('\n\n-----Publishing the (updating ownership error) message with routing_key=ownership.error-----')
            message = {
                "code": 400,
                "message_type": "ownership_error",
                "data": department_update_result
            }

            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='ownership.error', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("\nDepartment error - Code {} - published to the RabbitMQ Exchange:".format(code))
            return department_update_result
        
        # ownership of department updated
        else:
            message = {
                "code": 201,
                "message_type": 'department_ownership_put_request',
                "data": department_update_result
            }
            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='ownership.notify', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("------------ OWNERSHIP EDITED SUCCESSFULLY - {} ------------".format(department_update_result))
 

        amqp_setup.check_setup()


    #---------------------------------------------------------------------------------
    # get department of buyer
        buyer_department_result = invoke_http(
            f"{department_url}/{buyerId}",
            method="GET"
        )
        # buyer department not updated
        code = buyer_department_result['code']
        if code not in range(200,300):
            print('\n\n-----Publishing the (department error) message with routing_key=department.error-----')
            message = {
                "code": 400,
                "message_type": "department_error",
                "data": buyer_department_result
            }

            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='department.error', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("\nDepartment error - Code {} - published to the RabbitMQ Exchange:".format(code))
            return buyer_department_result
        
        # buyer department updated
        else:
            message = {
                "code": 201,
                "message_type": 'department_put_request',
                "data": buyer_department_result
            }
            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='department.notify', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("------------ DEPARTMENT EDITED SUCCESSFULLY - {} ------------".format(buyer_department_result))
            
        
        #adding item into buyer's department database and adding total carbon emission
        buyer_department_data = buyer_department_result['data']
        # store new item_id in department
        department_items = buyer_department_data['items']
        department_items.append(item_id)
        buyer_department_data['items'] = department_items
        # add carbon data to department
        department_carbon = buyer_department_data['totalCarbon']
        buyer_department_data['totalCarbon'] = department_carbon + item['carbonEmission']

        #invoke department url to update changes to buyer's database
        invoke_http(
            f"{department_url}/edit/{item['recievorId']}",
            method='PUT',
            json=item
        )
        


    #---------------------------------------------------------------------------------
    #slack notification
        slack_result = invoke_http(
                f"{slack_url}",
                method="POST",
                json=item
            )
        code = slack_result['code']
        slack_data = slack_result['data']
        
        if code not in range(200, 300):
            print('\n\n-----Publishing the (slack error) message with routing_key=slack.error-----')
                
            message = {
                "code": 400,
                "message_type": "business_error",
                "data": "Invalid slack response"
            }
            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='slack.error', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("\nSlack error - Code {} - published to the RabbitMQ Exchange:".format(code))
            return slack_result
        
        else:
            message = {
                "code": 201,
                    "message_type": 'slack_notification',
                    "data": slack_data
            }
            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='slack.notify', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("------------ SLACK NOTIFICATION SENT SUCCESSFULLY - {} ------------".format(slack_data))
            
    
    #---------------------------------------------------------------------------------
    # get department of seller
        seller_department_result = invoke_http(
            f"{department_url}/{sellerId}",
            method="GET"
        )

        if seller_department_result['code'] not in range(200,300):
            print('\n\n-----Publishing the (department error) message with routing_key=department.error-----')
            message = {
                "code": 400,
                "message_type": "department_error",
                "data": seller_department_result
            }

            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='department.error', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("\nDepartment error - Code {} - published to the RabbitMQ Exchange:".format(code))
            return seller_department_result
        
        else:
            message = {
                "code": 201,
                "message_type": 'department_put_request',
                "data": seller_department_result
            }
            message = json.dumps(message)
            amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key='department.notify', body=message, properties=pika.BasicProperties(delivery_mode=2))
            print("------------ DEPARTMENT EDITED SUCCESSFULLY - {} ------------".format(seller_department_result))
        

        #remove item from seller's and add carbon emission
        seller_department_data = seller_department_result['data']
        # store new item_id in department
        item_id = item['id']
        department_items = seller_department_data['items']
        department_items.pop(item_id)
        seller_department_data['items'] = department_items
        # add carbon data to department
        department_carbon = seller_department_data['totalCarbon']
        seller_department_data['totalCarbon'] = department_carbon + item['carbonEmission']
        

    #---------------------------------------------------------------------------------
    #handle error for 'change status of isListing from true to false'
    else:
        print('\n\n-----Publishing the item accept update message with routing_key=accept.error-----')        

        message = json.dumps({
            "code": 400,
            "message_type": "accept_error",
            "data": new_item_result
        })
        amqp_setup.channel.basic_publish(exchange=amqp_setup.exchangename, routing_key="accept.error", 
        body=message, properties=pika.BasicProperties(delivery_mode = 2)) 

        print("\nItem accept error published to RabbitMQ Exchange.\n")

        return jsonify({
            "code": 403,
            "message": f"Unable to accept item. Item status is already {new_item_result['isListing']}."
        })

    # ##################### END OF AMQP code

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5101, debug=True)

