
from django.db import models
from .models import Category, BlogPost

def blog_sidebar(request):
    """Context processor to add blog sidebar data to all templates"""
    # Get categories with post counts
    categories = Category.objects.annotate(
        post_count=models.Count('blogpost')
    ).filter(post_count__gt=0).order_by('-post_count')

    # Get recent posts (5 most recent)
    recent_posts = BlogPost.objects.filter(
        is_published=True
    ).order_by('-publish_date')[:5]

    # Get all tags from published posts
    all_tags = []
    posts_with_tags = BlogPost.objects.filter(
        is_published=True,
        tags__isnull=False
    ).exclude(tags='')

    for post in posts_with_tags:
        tags = post.get_tags_list()
        for tag in tags:
            if tag not in all_tags:
                all_tags.append(tag)

    # Sort tags alphabetically
    all_tags.sort()

    return {
        'sidebar_categories': categories,
        'recent_posts': recent_posts,
        'sidebar_tags': all_tags,
    }
