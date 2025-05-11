import json
from .lib.db import con, Model, SerializableRow
from .lib import chat, sd

class User(Model):
    table_name = 'users'

class Post(Model):
    table_name = 'posts'

    @classmethod
    def find_user(cls, user_id: int) -> list[SerializableRow]:
        return con.execute("SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()

    @classmethod
    def find_user_meta(cls, user_id: int) -> list[SerializableRow]:
        return con.execute("SELECT p.*, i.params FROM posts AS p LEFT JOIN images AS i ON i.id = p.image_id WHERE p.user_id = ?", (user_id,)).fetchall()

    @classmethod
    def find_latest(cls, limit: int=20) -> list[SerializableRow]:
        return con.execute(f"SELECT * FROM posts ORDER BY created_at DESC LIMIT {limit}").fetchall()

    @classmethod
    def generate(cls, user_id: int) -> int:
        user = User.find(id=user_id)

        # TODO: tune prompt to not give such Instagram-like posts, something more diverse would be better. Also fewer hashtags and Emoji.

        # Generate a post for the user
        conv = chat.OpenAIChat()
        posts = Post.find_user_meta(user_id)
        if posts:
            history = [{
                "role": "user",
                "content": f"Write a new post for {user['name']} ({user['pronouns']}).\nUser bio: {user['bio']}"
            }]
            if user['writing_style']:
                history[0]['content'] += f"\nWriting style:{user['writing_style']}"
            for post in posts:
                prompt = None
                if post['image_id']:
                    image_params = json.loads(post['params'])
                    prompt = image_params[0]['prompt'].partition("\n")[0]

                history.append({"role": "assistant", "content": json.dumps({
                    'post_body': post['body'],
                    'image_prompt': prompt,
                })})
                history.append({"role": "user", "content": "Write the next post for the user."})

            response = conv.schema_completion('post', "Write the next post for the user. The post does not have to be related to the bio or the user's other posts.", history)
        else:
            response = conv.schema_completion('post',
                    f"Write a new post for {user['name']} ({user['pronouns']}). User bio: {user['bio']}\n" +
                    "The post does not have to be related to the bio.",)

        # Generate an image for the post, if the LLM says it should.
        img_id = None
        if response.get('image_prompt'):
            img = sd.StableDiffusion()
            pic = img.txt2img(response['image_prompt'])
            img_id = Image.insert(user_id=user['id'], params=json.dumps(pic.params), data=pic.data)

        return Post.insert(user_id=user['id'], body=response['post_body'], image_id=img_id)

class Image(Model):
    table_name = 'images'

    @classmethod
    def find_user(cls, user_id: int) -> list[SerializableRow]:
        return con.execute("SELECT * FROM images WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()

class Comment(Model):
    table_name = 'comments'

    @classmethod
    def find_post(cls, post_id: int) -> list[SerializableRow]:
        return con.execute(f"SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC", (post_id,)).fetchall()

    @classmethod
    def generate(cls, post_id: int, user_id: int) -> int:
        user = User.find(id=user_id)
        post = Post.find(id=post_id)
        post_user = User.find(id=post['user_id'])

        # TODO: tune prompt to be more like a brief comment, not an entire Instagram post.

        # TODO: if the user and post_user are the same, use a prompt that explicitly tells the LLM they are commenting on their own post.

        # Generate a post for the user
        conv = chat.OpenAIChat()
        history = [{
            "role": "system",
            "content": f"You are {user['name']} ({user['pronouns']}). User bio: {user['bio']}\n You are writing a comment on the given social media post. It can be a reply to other comments (if any), or directly responding to the post itself. *Do not include any meta-text, only the comment body.*"
        }, {
            "role": "user",
            "content": f"Post by {post_user['name']} ({post_user['pronouns']}): {post['body']}",
        }]
        if user['writing_style']:
            history[0]['content'] += f"\nYour writing style:{user['writing_style']}"
        comments = Comment.find_post(post_id)
        for comment in comments:
            comment_user = User.find(id=comment['user_id'])
            history.append({
                "role": "user",
                "content": f"Comment by {comment_user['name']}: {comment['body']}" if comment_user else comment['body'],
            })
        response = conv.completions(None, history)

        return Comment.insert(user_id=user_id, post_id=post_id, body=response)

class Chat(Model):
    table_name = 'chats'

    @classmethod
    def find_user(cls, user_id: int) -> list[SerializableRow]:
        sql = "SELECT * FROM chats WHERE user_id = ? ORDER BY created_at ASC"
        return con.execute(sql, (user_id,)).fetchall()
