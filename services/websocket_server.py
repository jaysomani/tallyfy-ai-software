import asyncio
import requests
import websockets
import json
import logging
import socket
import datetime
import os
import signal
import sys

from backend.local_db_connector import LocalDbConnector

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

active_connections = set()
local_db = LocalDbConnector()
server = None

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except socket.error:
            return True

async def heartbeat(websocket, client_id):
    try:
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send(json.dumps({
                    "type": "heartbeat",
                    "timestamp": datetime.datetime.now().isoformat()
                }))
            except websockets.exceptions.ConnectionClosed:
                logger.info(f"Heartbeat failed for client {client_id} - connection closed")
                break
            except Exception as e:
                logger.error(f"Heartbeat error for client {client_id}: {e}")
                break
    except asyncio.CancelledError:
        pass

async def handle_websocket(websocket):
    client_id = id(websocket)
    logger.info(f"New WebSocket connection {client_id}")
    active_connections.add(websocket)
    heartbeat_task = asyncio.create_task(heartbeat(websocket, client_id))

    try:
        await websocket.send(json.dumps({
            "type": "connection",
            "status": "connected",
            "client_id": client_id
        }))

        async for message in websocket:
            try:
                msg_data = json.loads(message)
                logger.info("Received message: %s", msg_data)
                msg_type = msg_data.get("type")

                if msg_type == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))

                elif msg_type == "fetch_companies":
                    user_email = msg_data.get("user_email")
                    if user_email:
                        companies = local_db.get_user_companies(user_email)
                        await websocket.send(json.dumps({
                            "type": "companies_data",
                            "data": companies
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": "Missing user_email parameter."
                        }))

                elif msg_type == "fetch_bank_names":
                    user_email = msg_data.get("user_email")
                    company_id = msg_data.get("company_id")
                    if user_email and company_id:
                        bank_accounts = local_db.get_user_bank_accounts(user_email, company_id)
                        await websocket.send(json.dumps({
                            "type": "bank_names_data",
                            "data": bank_accounts
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": "Missing user_email or company_id parameter."
                        }))

                elif msg_type == "store_pdf_data":
                    user_email = msg_data.get("user_email")
                    company_id = msg_data.get("company_id")
                    bank_accounts = msg_data.get("bank_account")
                    pdf_data = msg_data.get("data")
                    fileName = msg_data.get("fileName")
                    logging.info(f"Recived PDF data via Websocket from user {user_email} for company {company_id}.")
                    try:
                        upload_id = local_db.upload_excel_local(user_email, company_id, bank_accounts, pdf_data, fileName)
                        await websocket.send(json.dumps({
                            "type": "store_pdf_response",
                            "status": "success",
                            "table": upload_id,
                            "fileName": fileName
                        }))
                    except Exception as e:
                        logging.error(f"Error storing PDF data: {e}")
                        await websocket.send(json.dumps({
                            "type": "store_pdf_response",
                            "status": "error",
                            "error": str(e)
                        }))

                elif msg_type == "fetch_temp_tables":
                    user_email = msg_data.get("user_email")
                    company = msg_data.get("company")
                    if user_email and company:
                        temp_tables = local_db.get_all_temp_tables(user_email, company)
                        logger.info("Returning temp tables for user %s and company %s: %s", user_email, company, temp_tables)
                        await websocket.send(json.dumps({
                            "type": "temp_tables_data",
                            "data": temp_tables
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": "Missing user_email or company parameter."
                        }))

                elif msg_type == "fetch_temp_table_data":
                    upload_id = msg_data.get("upload_id")
                    if upload_id:
                        rows = local_db.get_temp_table_data(upload_id)
                        await websocket.send(json.dumps({
                            "type": "temp_table_data",
                            "upload_id": upload_id,
                            "data": rows
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": "Missing upload_id in fetch_temp_table_data"
                        }))
                
                elif msg_type == "update_temp_excel":
                    upload_id = msg_data.get("tempTable")
                    update_data = msg_data.get("data")
                    if not upload_id or not update_data:
                        await websocket.send(json.dumps({
                            "type": "update_temp_excel_response",
                            "status": "error",
                            "error": "Missing tempTable or data"
                        }))
                    else:
                        try:
                            with local_db.engine.begin() as connection:
                                delete_stmt = local_db.temporary_transactions.delete().where(
                                    local_db.temporary_transactions.c.upload_id == upload_id
                                )
                                connection.execute(delete_stmt)

                            with local_db.engine.begin() as connection:
                                for row in update_data:
                                    let_date = row.get("transaction_date")
                                    jsDate = local_db.convert_date(let_date) if let_date else None
                                    # For transaction type, try both keys.
                                    txn_type = row.get("transaction_type") or row.get("type") or None
                                    # For assigned ledger, try both keys.
                                    assigned_ledger = row.get("assignedLedger") or row.get("assigned_ledger") or ""
                                    connection.execute(
                                        local_db.temporary_transactions.insert().values(
                                            upload_id=upload_id,
                                            email=row.get("email", ""),  # Ensure you pass the email
                                            company=row.get("company", ""),  # And the company
                                            bank_account=row.get("bank_account", ""),
                                            transaction_date=jsDate,
                                            transaction_type=txn_type,
                                            description=row.get("description", ""),
                                            amount=row.get("amount", 0),
                                            assigned_ledger=assigned_ledger
                                        )
                                    )
                            logger.info("Update for upload %s completed", upload_id)
                            await websocket.send(json.dumps({
                                "type": "update_temp_excel_response",
                                "status": "success",
                                "table": upload_id
                            }))
                        except Exception as e:
                            logger.exception("Error updating temp table data via websocket")
                            await websocket.send(json.dumps({
                                "type": "update_temp_excel_response",
                                "status": "error",
                                "error": str(e)
                            }))

                elif msg_type == "fetch_ledger_options":
                    company_id = msg_data.get("company_id")
                    if company_id:
                        ledger_options = local_db.get_ledger_options(company_id)
                        await websocket.send(json.dumps({
                            "type": "ledger_options",
                            "options": ledger_options
                        }))
                    else:
                        await websocket.send(json.dumps({
                            "type": "error",
                            "error": "Missing company_id parameter for ledger options."
                        }))
                elif msg_type == "send_to_tally":
                    company = msg_data.get("company")
                    tempTable = msg_data.get("tempTable")
                    selectedTransactions = msg_data.get("selectedTransactions")  # Can be null
                    if not company or not tempTable:
                        await websocket.send(json.dumps({
                            "type": "send_to_tally_response",
                            "status": "error",
                            "error": "Missing company or tempTable"
                        }))
                    else:
                        properCompanyName = local_db.get_company_name(company)
                        if not properCompanyName:
                            await websocket.send(json.dumps({
                                "type": "send_to_tally_response",
                                "status": "error",
                                "error": "Company not found in database"
                            }))
                            return
                        # Fetch transactions. If selectedTransactions is provided, filter by IDs.
                        if selectedTransactions and len(selectedTransactions) > 0:
                            transactions = local_db.get_transactions_by_ids(tempTable, selectedTransactions)
                        else:
                            transactions = local_db.get_temp_table_data(tempTable)
                        
                        # Filter transactions that have an assigned ledger.
                        transactions = [t for t in transactions if t.get("assigned_ledger", "").strip() != ""]
                        
                        if not transactions:
                            await websocket.send(json.dumps({
                                "type": "send_to_tally_response",
                                "status": "error",
                                "error": "No transactions found with assigned ledgers"
                            }))
                        else:
                            try:
                                # Instead of converting and sending to Tally directly here,
                                # forward the JSON data to your Flask endpoint.
                                flask_endpoint = "http://localhost:5000/api/tallyConnector"
                                payload = {
                                    "company": properCompanyName,
                                    "data": transactions
                                }
                                logger.info("Sending payload to Tally: %s", payload)
                                flask_response = requests.post(
                                    flask_endpoint,
                                    json=payload,  # sending as JSON so the Flask server can call request.get_json()
                                    timeout=10
                                )
                                
                                # After a successful call, update transaction statuses.
                                if selectedTransactions and len(selectedTransactions) > 0:
                                    local_db.update_transactions_status(tempTable, selectedTransactions, "sent")
                                else:
                                    local_db.update_transactions_status_all(tempTable, "sent")
                                
                                await websocket.send(json.dumps({
                                    "type": "send_to_tally_response",
                                    "status": "success",
                                    "message": "Data sent to Tally successfully",
                                    "transactionsSent": len(transactions),
                                    "tallyResponse": flask_response.json()  # or flask_response.text if preferred
                                }))
                            except Exception as e:
                                logger.exception("Error sending data to Tally")
                                await websocket.send(json.dumps({
                                    "type": "send_to_tally_response",
                                    "status": "error",
                                    "error": str(e)
                                }))

                else:
                    logger.debug("Unrecognized message type received: %s", msg_type)
                    await websocket.send(json.dumps({
                        "type": "error",
                        "error": f"Unrecognized message type: {msg_type}"
                    }))

            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received from client {client_id}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "error": "Invalid JSON format."
                }))
            except Exception as e:
                logger.exception(f"Error handling message from client {client_id}: {e}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "error": str(e)
                }))

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"WebSocket connection closed for client {client_id}")
    except Exception as e:
        logger.error(f"Unexpected error for client {client_id}: {e}")
    finally:
        active_connections.discard(websocket)
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

async def websocket_listener():
    global server
    port = 8000
    retries, delay = 5, 1
    
    while retries > 0:
        if is_port_in_use(port):
            logger.warning(f"Port {port} is in use, retrying in {delay}s...")
            await asyncio.sleep(delay)
            delay *= 2
            retries -= 1
            continue
            
        try:
            server = await websockets.serve(
                handle_websocket,
                "0.0.0.0",
                port,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10,
                max_size=10 * 1024 * 1024
            )
            logger.info(f"WebSocket server running at ws://localhost:{port}")
            
            # Use asyncio.Event for graceful shutdown instead of signals
            shutdown_event = asyncio.Event()
            
            # Wait for shutdown event
            await shutdown_event.wait()
            
            # Close server gracefully
            server.close()
            await server.wait_closed()
            break
            
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
            await asyncio.sleep(delay)
            delay *= 2
            retries -= 1
            if retries == 0:
                logger.error("Failed to start WebSocket server after maximum retries")
                raise

def start_websocket_server():
    try:
        # Create a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run the server
        loop.run_until_complete(websocket_listener())
    except KeyboardInterrupt:
        logger.info("WebSocket server stopped by user")
    except Exception as e:
        logger.error(f"WebSocket server failed: {e}")
        raise
    finally:
        # Clean up
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        
        # Wait for all tasks to complete
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

if __name__ == "__main__":
    start_websocket_server()
