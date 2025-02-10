from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from .models import Topic, Category, Post
from django.db.models.functions import Lower
from user_accounts.models import User
from notifications.models import Notification
from django.db.models import Case, When
from django.contrib.sessions.models import Session
from django.utils import timezone
from datetime import timedelta
from post_interactions.models import (
    Comment,
    Like,
    Dislike,
)
import base64

@login_required
def topic_detail(request, topic_title):
    topic = get_object_or_404(Topic, title=topic_title)
    posts = topic.posts.all().order_by('-created_at')

    paginator = Paginator(posts, 5)
    page = request.GET.get('page', 1)

    try:
        paginated_posts = paginator.page(page)
    except PageNotAnInteger:
        paginated_posts = paginator.page(1)
    except EmptyPage:
        paginated_posts = paginator.page(paginator.num_pages)

    return render(request, 'discussion_forum/topic_detail.html', {
        'topic': topic,
        'posts': paginated_posts,
    })

@login_required
def create_post(request):
    if request.method == 'POST':
        category_id = request.POST.get('category')
        topic_id = request.POST.get('topic')
        content = request.POST.get('content')
        
        if not content and 'media' not in request.FILES:
            return redirect('discussion_forum:forum_index')
        
        media_data = None
        media_type = None
        
        if 'media' in request.FILES:
            file = request.FILES['media']
            # Check file size (5MB limit)
            if file.size > 5 * 1024 * 1024:
                messages.error(request, "Dosya boyutu 5MB'dan küçük olmalı")
                return redirect('discussion_forum:forum_index')
            
            media_data = base64.b64encode(file.read()).decode('utf-8')
            media_type = file.content_type
            
        category = get_object_or_404(Category, id=category_id)

        post = Post(
            author=request.user,
            content=content,
            category=category,
            media_data=media_data,
            media_type=media_type
        )
        
        if topic_id:
            topic = get_object_or_404(Topic, id=topic_id)
            post.topic = topic
            
        post.save()
        
        return redirect('discussion_forum:forum_index')
    
    return redirect('discussion_forum:forum_index')

@login_required
def get_topics(request, category_id):
    topics = Topic.objects.filter(category_id=category_id).values('id', 'title')
    return JsonResponse({'topics': list(topics)})

def update_user_activity(request):
    if request.user.is_authenticated:
        request.session['last_activity'] = timezone.now()
        request.user.last_activity = timezone.now()
        request.user.save()

@login_required
def forum_index(request):
    categories = Category.objects.annotate(
        custom_order=Case(
            When(name='Gündem', then=0),
            default=1,
        )
    ).order_by('custom_order', 'name')
    all_posts = Post.objects.select_related('author', 'topic', 'topic__category').order_by('-created_at')
    
    all_users = User.objects.order_by(Lower('username'))
    
    search_query = request.GET.get('search', '').lower()
    if search_query:
        all_users = all_users.filter(username__icontains=search_query)

    paginator = Paginator(all_posts, 10)
    page = request.GET.get('page', 1)

    total_users = User.objects.count()
    total_posts = Post.objects.count()
    total_categories = Category.objects.count()
    
    active_sessions = Session.objects.filter(expire_date__gte=timezone.now()).count()

    # Son 15 dakikada aktif olan kullanıcılar
    active_time_threshold = timezone.now() - timedelta(minutes=2)
    active_users = User.objects.filter(last_login__gte=active_time_threshold)

    active_users_count = active_users.count()

    active_users_names = [user.username for user in active_users]
    active_users_count = len(active_users_names)

    try:
        latest_posts = paginator.page(page)
    except PageNotAnInteger:
        latest_posts = paginator.page(1)
    except EmptyPage:
        latest_posts = paginator.page(paginator.num_pages)

    return render(request, 'discussion_forum/forum_index.html', {
        'categories': categories,
        'latest_posts': latest_posts,
        'users': all_users,
        'stats': {
            'total_users': total_users,
            'total_posts': total_posts,
            'total_categories': total_categories,
            'active_users': ', '.join(active_users_names)
        }
})

@login_required
def category_topics(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    topics = category.topics.all().order_by('title')
    direct_posts = Post.objects.filter(category=category, topic__isnull=True).order_by('-created_at')
    
    paginator = Paginator(direct_posts, 6)  
    page = request.GET.get('page', 1)
    try:
        paginated_posts = paginator.page(page)
    except PageNotAnInteger:
        paginated_posts = paginator.page(1)
    except EmptyPage:
        paginated_posts = paginator.page(paginator.num_pages)
    
    return render(request, 'discussion_forum/category_topics.html', {
        'category': category,
        'topics': topics,
        'direct_posts': paginated_posts,
    })

@login_required
def post_detail(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == 'POST':
        if 'edit_post' in request.POST:
            if post.author == request.user or request.user.is_staff:
                edited_content = request.POST.get('edited_post_content')
                post.content = edited_content
                
                # Medya işlemleri
                remove_media = request.POST.get('remove_media') == 'true'
                if remove_media:
                    post.media_data = None
                    post.media_type = None
                
                if 'edited_media' in request.FILES:
                    file = request.FILES['edited_media']
                    if file.size > 5 * 1024 * 1024:
                        raise ValidationError("Dosya boyutu 5MB'dan küçük olmalı")
                    
                    post.media_data = base64.b64encode(file.read()).decode('utf-8')
                    post.media_type = file.content_type
                
                post.save()
                return redirect('discussion_forum:post_detail', post_id=post.id)
            
        elif 'delete_post' in request.POST:
            if post.author == request.user or request.user.is_staff:
                post.delete()
                return redirect('discussion_forum:forum_index') 
            
        elif 'comment' in request.POST:
            comment_content = request.POST.get('comment_content')
            media_data = None
            media_type = None

            if 'media' in request.FILES:
                file = request.FILES['media']
                # Dosya boyutu kontrolü (örn: 5MB)
                if file.size > 5 * 1024 * 1024:
                    raise ValidationError("Dosya boyutu 5MB'dan küçük olmalı")
                
                # Base64'e çevir
                media_data = base64.b64encode(file.read()).decode('utf-8')
                media_type = file.content_type

            if comment_content or media_data:
                comment = Comment.objects.create(
                    post=post,
                    author=request.user,
                    content=comment_content,
                    media_data=media_data,
                    media_type=media_type
                )
                
                if post.author != request.user:
                    Notification.objects.create(
                        user=post.author,
                        message=f"{request.user.username}, {post.content[:30]}... gönderine yorum yaptı!",
                        notification_type='comment',
                        related_object_id=post.id
                    )

        elif 'edit_comment' in request.POST:
            comment_id = request.POST.get('comment_id')
            edited_content = request.POST.get('edited_content')
            comment = get_object_or_404(Comment, id=comment_id)

            if comment.author == request.user or request.user.is_staff:
                comment.content = edited_content
                comment.save()
                
        elif 'delete_comment' in request.POST:
            comment_id = request.POST.get('comment_id')
            comment = get_object_or_404(Comment, id=comment_id)
            
            if comment.author == request.user:
                comment.delete()

        elif 'like' in request.POST:
            like = post.likes.filter(user=request.user).first()
            if like:
                like.delete()  
            else:
                Like.objects.create(user=request.user, post=post) 
                
                if post.author != request.user:
                    Notification.objects.create(
                        user=post.author,
                        message=f"{request.user.username}, {post.content[:30]}... gönderine emoji bıraktı!",
                        notification_type='like',
                        related_object_id=post.id,
                        post=post 
                    )

        elif 'dislike' in request.POST:
            dislike = post.dislikes.filter(user=request.user).first()
            if dislike:
                dislike.delete()  
            else:
                Dislike.objects.create(user=request.user, post=post) 
                
                if post.author != request.user:
                    Notification.objects.create(
                        user=post.author,
                        message=f"{request.user.username}, {post.content[:30]}... gönderine emoji bıraktı!",
                        notification_type='dislike',
                        related_object_id=post.id,
                        post=post 
                    )

        return redirect('discussion_forum:post_detail', post_id=post.id)
    
    
    comments = post.comments.all()
    likes_count = post.likes.count()
    dislikes_count = post.dislikes.count()
    user_likes = post.likes.filter(user=request.user).exists()
    user_dislikes = post.dislikes.filter(user=request.user).exists()

    return render(request, 'discussion_forum/post_detail.html', {
        'post': post,
        'comments': comments,
        'likes_count': likes_count,
        'dislikes_count': dislikes_count,
        'user_likes': user_likes,
        'user_dislikes': user_dislikes,
    })
