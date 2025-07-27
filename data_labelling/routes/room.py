import json

from flask import Blueprint, render_template, redirect, request, jsonify, g
from flask_socketio import emit

from ..utils import *
from ..models import *
from ..match_making import leave_room
import os
import base64
from werkzeug.utils import secure_filename
bp = Blueprint('room_bp', __name__)


@bp.route('/<int:room_id>/messages')
@room_guard
def get_messages(room):
    def wrap(message):
        message['payload'] = bool(message['payload'])
        return message
    return jsonify([wrap(message) for message in room.messages.select(Message.id, Message.role, Message.content, Message.payload,Message.typefile).dicts()])


@bp.route('/<int:room_id>/<int:role>/message/content', methods=['POST'])
@room_guard
def post_message_content(room, role):
    try:
        data = request.get_data()
        data = json.loads(data)
        content = data['content']
        # emit('update', namespace='/room/%s' % (room.id), broadcast=True)
        # emit('update', namespace='/room/%s/0' % (room.id), broadcast=True)
        # emit('update', namespace='/room/%s/1' % (room.id), broadcast=True)
    except:
        return '格式错误', 400
    try:
        lastmsg = Message.select().where(Message.room == room).order_by(-Message.id).first()
        if lastmsg.role == role:
            return '不得连续两次发送消息', 403
        elif not lastmsg.payload:
            return '对方尚未提交表单', 403
    except:
        pass
    Message.create(room=room, role=role, content=content, payload={})
    emit('update', namespace='/room/%s' % (room.id), broadcast=True)
    # emit('update', namespace='/room/%s/0' % (room.id), broadcast=True)
    # emit('update', namespace='/room/%s/1' % (room.id), broadcast=True)
    return 'OK'

@bp.route('/<int:room_id>/<int:role>/message/payload', methods=['POST'])
@room_guard
def post_message_payload(room, role):
    try:
        data = request.get_data()
        data = json.loads(data)
        payload = data['payload']
        # emit('update', namespace='/room/%s' % room.id, broadcast=True)
    except:
        return '格式错误', 400
    try:
        lastmsg = Message.select().where(Message.room == room).order_by(-Message.id).first()
        if lastmsg.role != role:
            return '上一次不是己方发送消息', 403
        elif lastmsg.payload:
            # emit('update', namespace='/room/%s' % room.id, broadcast=True)
            return '已经提交表单', 403
    except:
        pass
    lastmsg.payload = payload
    lastmsg.save()
    emit('update', namespace='/room/%s' % room.id, broadcast=True)
    return 'OK'

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'JPG', 'PNG', 'bmp'])
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS
@bp.route('/<int:room_id>/<int:role>/picture/submit', methods=['POST'])
@room_guard
def post_picture_submit(room, role):
    f=request.files['file']
    if not (f and allowed_file(f.filename)):
        return '文件错误', 403
    basepath=os.path.dirname(__file__)
    upload_path=os.path.join(basepath, '../static/picture',secure_filename(f.filename))
    f.save(upload_path)
    upload_path_for_send='<'+str(upload_path)+'>'
    upload_path_for_send='/static/picture/'+str(f.filename)
    with open(upload_path,"rb") as file2:#转为二进制格式
        base64_data = base64.b64encode(file2.read())
    # base64_data="https://i.loli.net/2019/05/20/5ce235620b61e34576.jpg"
    Message.create(room=room, role=role, content=upload_path_for_send,payload={},typefile=False)
    return 'OK'


@bp.route('/<int:room_id>/<int:role>')
@room_guard
def room(room, role):
    return render_template('room.html', room=room, role=role)


@bp.route('/<int:room_id>/leave')
@room_guard
def leave(room):
    if not room.user1 == g.me:
        return '只有用户可以结束任务', 400
    try:
        lastmsg = Message.select().where((Message.room == room) & (Message.role == 1)).order_by(-Message.id).first()
        if not lastmsg:
            return '还没消息', 403
        # gugu = lastmsg.payload
        # for item in gugu:
        #     if not item[3]:
        #         return '表单没填完', 403
    except:
        pass

    room.status = Room.Status.SUCCESS
    room.save()

    close_room(room)

    emit('finished', namespace='/room/%s' % room.id, broadcast=True)
    return 'OK'


@bp.route('/<int:room_id>/abort')
@room_guard
def abort(room):
    task = room.task
    task.finished = False
    task.save()

    room.status = Room.Status.ABORTED
    room.save()

    close_room(room)

    emit('finished', namespace='/room/%s' % room.id, broadcast=True)
    return 'OK'


def close_room(room):
    leave_room(room.user0.id)
    leave_room(room.user1.id)
    room.user0.updateTasksCount()
    room.user1.updateTasksCount()
