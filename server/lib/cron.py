import multiprocessing
import random
import time

from ..models import Post, User, Comment

def run_every(func, minutes: int=10, *args, **kwargs):
    def wrapper():
        while True:
            time.sleep(minutes * 60)
            func(*args, **kwargs)

    # TODO: use event signalling to gracefully stop process instead of killing it (daemon=False + custom handler)

    ctx = multiprocessing.get_context('fork')
    process = ctx.Process(target=wrapper)
    process.daemon = True
    process.start()


def _post():
    users = User.find_all(is_active=1, is_human=0)
    user = random.choice(users)
    print(f'Writing a post for {user['name']}')
    Post.generate(user['id'])


def post_every(minutes: int=10):
    run_every(_post, minutes)


def _comment(max: int=5):
    posts = Post.find_latest()
    post = random.choice(posts)
    comments = Comment.find_post(post['id'])
    if len(comments) > max:
        return
    users = User.find_all(is_active=1, is_human=0)
    user = random.choice(users)
    print(f'Writing a comment by {user['name']} for post {post['id']}')
    Comment.generate(post['id'], user['id'])


def comment_every(minutes: int=1):
    run_every(_comment, minutes)
