from telegram import (Poll, ParseMode, KeyboardButton, KeyboardButtonPollType, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Updater, CommandHandler, PollAnswerHandler, PollHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler, ConversationHandler, Filters)
import time
import datetime
import random
import json
import threading
import operator
from array import *

# START, ENVIA EL MENU O VERIFICA SI HAY UNA PETICION PARA ENTRAR A UNA SALA
def start(update, context):
    global msgMainMenu, currentRooms, currentPlayers
    userId = update.effective_user.id
    chatId = update.effective_chat.id
    # SI ES UN CHAT PRIVADO Y EL USUARIO SE ENCUENTRA EN UNA SALA ENVIA UNA ADVERTENCIA
    if update.effective_chat.type == "private" and currentPlayers.get(userId) != None:
        update.message.reply_text("Hay una partida en curso, usa el comando /stop para cerrarla." if currentPlayers[userId]["room_id"] == chatId else "Ya te encuentras en una sala, primero usa el comando /stop para salir.")
        return
    # SI ES UN CHAT PRIVADO Y EL USUARIO QUIERE ENTRAR EN UNA SALA CUANDO ESTA EN OTRA ENVIA UNA ADVERTENCIA O SINO ENTRA
    messageParameters = update.message.text.split(" ")
    if (len(messageParameters) == 2) and currentRooms.get(int(messageParameters[1])) != None:
        if update.effective_chat.type == "private":
            message = ""
            room = currentRooms.get(int(messageParameters[1]))
            if room != None:
                if room["running"] == 0:
                    numPlayers = len(room["players"])
                    if numPlayers <= room["max_players"]:
                        currentRooms[room["chat_id"]]["players"][userId] = {"user": update.effective_user, "stats": []}
                        currentPlayers[userId] = {"id": userId, "room_id": room["chat_id"]}
                        msgRoom = createRoomMsg(room["room_name"], currentRooms[room["chat_id"]]["players"], room["max_players"], room["chat_id"])
                        context.bot.edit_message_text(chat_id=room["chat_id"], message_id=room["message_id"], text=msgRoom["text"], reply_markup=msgRoom["markup"])
                        message = f'Te haz unido a la sala creada por {room["players"][room["admin_id"]]["user"]["first_name"]}.\n\nUsa el comando /stop para salir.'
                    else:
                        message = "No puedes unirte, la sala se encuentra llena."
                else:
                    message = "No puedes unirte, la partida ya ha comenzado."
            else:
                message = "No se ha encontrado la sala, puede que se haya cerrado."
            update.message.reply_text(message)
            return
    update.message.reply_text(text=msgMainMenu["text"], reply_markup=msgMainMenu["markup"])

def selectGameMode(update, context):
    global msgGameModes
    update.callback_query.answer()
    update.callback_query.edit_message_text(text=msgGameModes["text"], reply_markup=msgGameModes["markup"])

def createRandomRoom(update, context):
    createRoom(update, context, "RANDOM", "random", 10, 3)

def createHardRoom(update, context):
    createRoom(update, context, "HARD", "random", 15, 2)

# ! Terminar la sala custom
def createCustomRoom(update, context):
    createRoom(update, context, "CUSTOM", "custom", 15, 30)

def createRoom(update, context, roomName, quizzesTheme, quizzesNum, quizTime):
    global currentRooms, currentPlayers
    chatType = update.effective_chat.type
    chatId = update.effective_chat.id
    userId = update.effective_user.id
    if currentRooms.get(chatId) == None:
        currentRooms[chatId] = {
            "chat_id": chatId,
            "room_name": roomName,
            "admin_id": userId,
            "players": {userId: {"user": update.effective_user, "stats": []}},
            "max_players": 10,
            "quizzes_theme": quizzesTheme,
            "quizzes_num": quizzesNum,
            "quiz_time": quizTime,
            "remaining_quizzes": 0,
            "running": 0,
            "message_id": update.callback_query.message.message_id
        }
        currentPlayers[userId] = {"id": userId, "room_id": chatId}
        if chatType == "group":
            msgRoom = createRoomMsg(roomName, currentRooms[chatId]["players"], 10, chatId)
            update.callback_query.answer()
            update.callback_query.edit_message_text(text=msgRoom["text"], reply_markup=msgRoom["markup"])
        else:
            update.callback_query.answer()
            threading.Thread(target=runRoom, args=(update, context, chatId)).start()
    else:
        context.bot.answer_callback_query(callback_query_id=update.callback_query.id, text="Ya hay una sala iniciada.", show_alert=True)

def leaveRoom(update, context):
    global currentRooms, currentPlayers, currentPolls
    userId = update.effective_user.id
    if currentPlayers.get(userId) != None:
        room = currentRooms[currentPlayers[userId]["room_id"]]
        if room["running"] == 0:
            if room["admin_id"] == userId:
                closeRoom(context, room["chat_id"])
                context.bot.edit_message_text(chat_id=room["chat_id"], message_id=room["message_id"], text=f"{update.effective_user.first_name} ha cerrado la sala.")
        else:
            playersActive = 0
            for p in room["players"]:
                player = currentPlayers.get(room["players"][p]["user"].id)
                playersActive += 1 if player != None and (player["room_id"] == room["chat_id"]) else 0
            if room["admin_id"] == userId or ((playersActive < 2 and len(room["players"]) > 1) or playersActive == 0):
                currentRooms[room["chat_id"]]["running"] = 0
            else:
                for p in room["players"][userId]["stats"]:
                    poll = currentPolls[p]
                    if poll["is_closed"] == False:
                        context.bot.stop_poll(room["chat_id"], poll["message_id"])
                        currentPolls[p]["is_closed"] = True
                del(currentPlayers[userId])


        if room["admin_id"] == userId:
            if room["running"] == 0:
                closeRoom(context, room["chat_id"])
                context.bot.edit_message_text(chat_id=room["chat_id"], message_id=room["message_id"], text=f"{update.effective_user.first_name} ha cerrado la sala.")
            # else:
        else:
            playersActive = 0
            for p in room["players"]:
                if currentPlayers.get(room["players"][p]["user"].id):
                    playersActive += 1
            if (playersActive < 2 and len(room["players"]) > 1) or playersActive == 0:
                if room["running"] == 0:
                    currentRooms[room["chat_id"]]["running"] = 0
                else:
                    removeRoom(context, room["chat_id"])
                    context.bot.edit_message_text(chat_id=room["chat_id"], message_id=room["message_id"], text=f"{update.effective_user.first_name} ha cerrado la sala.")
            else:
                if room["running"] == 0:
                    del(currentRooms[currentPlayers[update.effective_user.id]["room_id"]]["players"][update.effective_user.id])
                    msgRoom = createMsgRoom(room["room_name"], room["players"], room["max_players"], room["chat_id"])
                    context.bot.edit_message_text(chat_id=room["chat_id"], message_id=room["message_id"], text=msgRoom["text"], reply_markup=msgRoom["markup"])


def createRoomMsg(gameType, players, maxPlayers, roomId):
    playersList = ""
    for player in players:
        playersList += f'\n- {players[player]["user"].first_name}'
    return {"text": f"⛳️ SALA {gameType} ⛳️\n\nJugadores ({len(players)}/{maxPlayers}): {playersList}", "markup": InlineKeyboardMarkup([
        [InlineKeyboardButton(text="Empezar ▶️", callback_data="play")],
        [InlineKeyboardButton(text="Unirme 🎟", url="t.me/GQuizzyBot?start="+repr(roomId))],
        [InlineKeyboardButton(text="Cerrar sala 🚪", callback_data="close_room")]
    ])}

# def createRoomStatsMsg(room_id):
#     global currentRooms, currentPolls
#     room = currentRooms.get(room_id)
#     if room != None:
#         stats = {}
#         for player in room["players"]:
#             stats[player] = 0
#             for poll_id in room["players"][player]["stats"]:
#                 if currentPolls[poll_id]["correct_answer"] == True:
#                     stats[player] += 10
#         playersList = ""
#         for player in enumerate(sorted(stats.items(), key=operator.itemgetter(1), reverse=True)):
#             player_id = player[1][0]
#             positions = {"1": "🥇 -", "2": "🥈 -", "3": "🥉 -"}
#             playerPosition = positions[repr(player[0] + 1)] if positions.get(repr(player[0] + 1)) != None else "-"
#             playersList += f'\n{playerPosition} {room["players"][player_id]["user"].first_name} ({stats[player_id]}pts)'
#         return f'🏁 PARTIDA {room["room_name"]} 🏁\n\nResultados:{playersList}'

if __name__ == "__main__":
    updater = Updater(token="1766886291:AAHjAYkw0CABjwkxz36JharmR8IuYcYA4-I")
    dp = updater.dispatcher
    dp.add_handler(ConversationHandler(entry_points=[
        CommandHandler("start", start),
        CallbackQueryHandler(pattern="start", callback=start),
        CallbackQueryHandler(pattern="select_gamemode", callback=selectGameMode),
        CallbackQueryHandler(pattern="create_random_room", callback=createRandomRoom),
        CallbackQueryHandler(pattern="create_hard_room", callback=createHardRoom),
        CallbackQueryHandler(pattern="create_custom_room", callback=createCustomRoom),
    ], states={}, fallbacks=[]))

    currentRooms = {}
    currentPlayers = {}
    currentPolls = {}

    msgMainMenu = {"text": "🎃 GQuizzy Version 0.4 🎃", "markup": InlineKeyboardMarkup([
        [InlineKeyboardButton(text="Jugar 🎮", callback_data="select_gamemode")],
        [InlineKeyboardButton(text="Ranking global 🏆", callback_data="ranking")],
        [InlineKeyboardButton(text="Ayuda ℹ️", callback_data="help")]
    ])}

    msgGameModes = {"text": "Modos de juego:", "markup": InlineKeyboardMarkup([
        [InlineKeyboardButton(text="Random 🎲", callback_data="create_random_room")],
        [InlineKeyboardButton(text="Hard ⏳", callback_data="create_hard_room")],
        [InlineKeyboardButton(text="Custom 🏝", callback_data="create_custom_room")],
    ])}

    updater.start_polling()
    updater.idle()