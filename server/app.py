import json
import random
from flask import Flask, jsonify, request, abort

from .lib import db, chat, sd, cron
from .models import User, Post, Comment, Image, Chat


# cron.post_every(10)
# cron.comment_every(2)

app = Flask(__name__)


@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"error": 404}), 404


@app.route('/')
def hello():
    return jsonify("Welcome to the SparklAI API!")


@app.route('/users')
def get_users():
    users = User.find_all(is_human=0, is_active=1)
    return jsonify([user.asdict() for user in users])


@app.route('/users/<int:id>')
def get_user(id):
    user = User.find(id=id)
    if user is None:
        abort(404)
    return jsonify(user.asdict())


# TODO: add routes and UI for deleting users, posts, comments, images.
@app.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    User.delete(id)
    return '', 204


@app.route('/users/<int:user_id>/posts')
def get_user_posts(user_id):
    posts = Post.find_user(user_id)
    return jsonify([post.asdict() for post in posts])


@app.route('/users/<int:user_id>/images')
def get_user_images(user_id):
    images = Image.find_user(user_id)
    response = []
    for i in images:
        response.append({
            "id": i['id'],
            "params": i['params'],
        })
    return jsonify(response)


@app.route('/users/<int:user_id>/posts', methods=['POST'])
def generate_user_post(user_id):
    post_id = Post.generate(user_id)
    return jsonify(post_id), 201


@app.route('/users', methods=['POST'])
def generate_user(user_prompt: str|None = None):
    # Generate a user
    conv = chat.OpenAIChat()
    profiles = []
    users = User.find_all()
    for user in users:
        profiles.append(f"- {user['name']} ({user['pronouns']}): {user['bio']}")
    # TODO: allow user to give additional prompt on how to create the user.
    prompt = "Create a new user profile. Do not duplicate an existing user!"
    if len(users):
        prompt += f" Current users are:\n{'\n'.join(profiles)}"
    if user_prompt:
        prompt += "\n" + user_prompt
    response = conv.schema_completion('user', prompt)
    id = User.insert(
        name=response['name'],
        age=response['age'],
        pronouns=response['pronouns'],
        bio=response['bio'],
        location=response['location'],
        occupation=response['occupation'],
        interests=response['interests'],
        personality_traits=response['personality_traits'],
        relationship_status=response['relationship_status'],
        writing_style=response['writing_style'],
        appearance=response['appearance'],
        backstory_snippet=response['backstory_snippet'],
    )

    # Generate a profile image
    # TODO: this should probably just call Image.generate_user() in another thread, async.
    # if response.get('appearance'):
    #     img = sd.StableDiffusion()
    #     pic = img.txt2img(json.dumps(response['appearance']))
    #     img_id = Image.insert(user_id=id, params=pic.params, data=pic.data)
    #     User.update(id, image_id=img_id)

    # Add their first post
    if response.get('example_post_body'):
        Post.insert(user_id=id, body=response['example_post_body'])

    user = User.find(id=id)
    return jsonify(user.asdict()), 201


@app.route('/users/<int:user_id>/image', methods=['POST'])
def generate_user_image(user_id):
    img_id = Image.generate_user(user_id)
    User.update(user_id, image_id=img_id)
    return jsonify(img_id), 201


@app.route('/posts')
def get_posts():
    posts = Post.find_latest()
    return jsonify([post.asdict() for post in posts])


@app.route('/posts/<int:id>')
def get_post(id):
    post = db.fetch_post(id)
    if post is None:
        abort(404)
    return jsonify(post.asdict())


@app.route('/posts/<int:id>', methods=['DELETE'])
def delete_post(id):
    Post.delete(id)
    return jsonify({"success": True}), 204


@app.route('/posts/<int:id>/comments')
def get_post_comments(id):
    comments = Comment.find_post(id)
    response = [comment.asdict() for comment in comments]
    for c in response:
        c['user'] = User.find(id=c['user_id']).asdict() if c['user_id'] else None
    return jsonify(response)


@app.route('/posts/<int:post_id>/comments', methods=['POST'])
def create_post_comment(post_id):
    id = Comment.insert(post_id=post_id, body=request.form['message'])
    return jsonify(Comment.find(id=id).asdict())


@app.route('/posts/<int:post_id>/respond', methods=['POST'])
def generate_post_comment(post_id):
    users = User.find_all()
    user = random.choice(users)
    id = Comment.generate(post_id, user['id'])
    response = Comment.find(id=id).asdict()
    response['user'] = user.asdict()
    return jsonify(response), 201


@app.route('/images/<int:id>', methods=['GET'])
def get_image(id):
    image = Image.find(id=id)
    if image is None:
        # TODO: custom handler for image 404s?
        abort(404)
    return image['data'], {
        'Content-Type': 'image/webp',
        'Cache-Control': 'public, max-age=604800',
    }


@app.route('/posts/<int:id>/image', methods=['POST'])
def create_post_image(id):
    post = db.fetch_post(id)
    if post is None:
        abort(404)

    # Generate an image prompt
    conv = chat.OpenAIChat()
    response = conv.schema_completion('post_image', post['body'])

    # Generate the image
    img = sd.StableDiffusion()
    pic = img.txt2img(response['image_prompt'])
    img_id = Image.insert(user_id=post['user_id'], params=pic.params, data=pic.data)

    Post.update(id, image_id=img_id)
    post_dict = post.asdict()
    post_dict['image_id'] = img_id

    return jsonify(post_dict), 200


@app.route('/chats/<int:user_id>', methods=['GET'])
def get_chats(user_id):
    chats = Chat.find_user(user_id)
    return jsonify([c.asdict() for c in chats])


@app.route('/chats/<int:user_id>', methods=['POST'])
def create_chat(user_id):
    # TODO: support uploading a photo for the AI to view (when vision-enabled model is used)
    id = Chat.insert(user_id=user_id, role='user', message=request.form['message'])
    return jsonify(Chat.find(id=id).asdict()), 201


@app.route('/chats/<int:user_id>/respond', methods=['POST'])
def create_chat_response(user_id):
    user = User.find(id=user_id)
    if user is None:
        abort(404)
    chats = Chat.find_user(user_id)
    conv = chat.OpenAIChat()
    history = [{
        'role': 'system',
        'content': f"You are {user['name']} ({user['pronouns']}), having an IM conversation.\n" +
            f"Your bio: {user['bio']}\n" +
            f"Writing style: {user['writing_style']}\n" +
            "Do not include any roleplay metatext, just write the actual response."
    }]
    for c in chats:
        history.append({
            'role': c['role'],
            'content': c['message']
        })
    # TODO: support also requesting schema'd response with image description for chat messages that should have images.
    response = conv.completions(None, history)
    res_id = Chat.insert(user_id=user_id, role='assistant', message=response) # type: ignore
    return jsonify(Chat.find(id=res_id).asdict()), 201


# Handle default headers
@app.after_request
def after_request(response):
    if response.headers is not None:
        response.headers['Access-Control-Allow-Origin'] = '*'
    return response
