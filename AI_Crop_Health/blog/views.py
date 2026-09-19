from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages
from .models import BlogPost, Comment, Category

def blog_list(request):
    """Blog listing page"""
    posts = BlogPost.objects.filter(is_published=True).order_by('-publish_date')
    paginator = Paginator(posts, 6)  # Show 6 posts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'blog/blog.html', {'page_obj': page_obj})

def blog_search(request):
    """Blog search functionality"""
    query = request.GET.get('q', '')
    if query:
        posts = BlogPost.objects.filter(
            Q(is_published=True) & (
                Q(title__icontains=query) |
                Q(content__icontains=query) |
                Q(excerpt__icontains=query) |
                Q(tags__icontains=query)
            )
        ).order_by('-publish_date')
    else:
        posts = BlogPost.objects.filter(is_published=True).order_by('-publish_date')

    paginator = Paginator(posts, 6)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'query': query,
        'is_search': True
    }
    return render(request, 'blog/blog.html', context)

def blog_detail(request, blog_id):
    """Blog detail page"""
    post = get_object_or_404(BlogPost, pk=blog_id, is_published=True)
    # Order comments to ensure parent comments come before replies
    comments = Comment.objects.filter(post=post, is_approved=True).order_by('created_date')
    context = {
        'post': post,
        'comments': comments,
    }
    return render(request, 'blog/blog-details.html', context)

def category_detail(request, category_slug):
    """Category detail page"""
    category = get_object_or_404(Category, slug=category_slug)
    posts = BlogPost.objects.filter(category=category, is_published=True).order_by('-publish_date')
    paginator = Paginator(posts, 6)  # Show 6 posts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'category': category,
        'page_obj': page_obj,
    }
    return render(request, 'blog/blog.html', context)

def tag_detail(request, tag_slug):
    """Tag detail page"""
    posts = BlogPost.objects.filter(
        is_published=True,
        tags__icontains=tag_slug
    ).order_by('-publish_date')
    paginator = Paginator(posts, 6)  # Show 6 posts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'tag': tag_slug,
        'page_obj': page_obj,
    }
    return render(request, 'blog/blog.html', context)

def add_comment(request, blog_id):
    """Add comment to blog post"""
    post = get_object_or_404(BlogPost, pk=blog_id, is_published=True)

    if request.method == 'POST':
        author_name = request.POST.get('name', '').strip()
        author_email = request.POST.get('email', '').strip()
        author_website = request.POST.get('website', '').strip()
        content = request.POST.get('comment', '').strip()
        parent_id = request.POST.get('parent_id', '').strip()

        # Validate required fields
        errors = []
        if not author_name:
            errors.append('Name is required.')
        elif len(author_name) < 2:
            errors.append('Name must be at least 2 characters long.')
        elif len(author_name) > 100:
            errors.append('Name cannot exceed 100 characters.')

        if not author_email:
            errors.append('Email is required.')
        elif '@' not in author_email or '.' not in author_email:
            errors.append('Please enter a valid email address.')

        if not content:
            errors.append('Comment content is required.')
        elif len(content) < 10:
            errors.append('Comment must be at least 10 characters long.')
        elif len(content) > 1000:
            errors.append('Comment cannot exceed 1000 characters.')

        if author_website and not (author_website.startswith('http://') or author_website.startswith('https://')):
            author_website = 'http://' + author_website

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Handle parent comment for replies
                parent_comment = None
                if parent_id and parent_id.isdigit():
                    try:
                        parent_comment = Comment.objects.get(pk=int(parent_id), post=post)
                    except Comment.DoesNotExist:
                        pass  # Invalid parent_id, treat as regular comment

                comment = Comment.objects.create(
                    post=post,
                    author_name=author_name,
                    author_email=author_email,
                    author_website=author_website,
                    content=content,
                    parent=parent_comment
                )
                messages.success(request, 'Your comment has been posted successfully!')
            except Exception as e:
                messages.error(request, f'An error occurred while posting your comment: {str(e)}')

    return redirect('blog:detail', blog_id=blog_id)

def user_panel(request):
    """User panel for logged-in users"""
    if not request.user.is_authenticated:
        return redirect('login')

    user_posts = BlogPost.objects.filter(author=request.user).order_by('-publish_date')
    user_comments = Comment.objects.filter(author_email=request.user.email).order_by('-created_date')

    context = {
        'user_posts': user_posts,
        'user_comments': user_comments,
    }
    return render(request, 'blog/user_panel.html', context)

def admin_panel(request):
    """Admin panel for staff users"""
    if not request.user.is_staff:
        return redirect('index')

    total_posts = BlogPost.objects.count()
    published_posts = BlogPost.objects.filter(is_published=True).count()
    total_comments = Comment.objects.count()
    approved_comments = Comment.objects.filter(is_approved=True).count()
    recent_posts = BlogPost.objects.order_by('-publish_date')[:5]
    recent_comments = Comment.objects.order_by('-created_date')[:5]

    context = {
        'total_posts': total_posts,
        'published_posts': published_posts,
        'total_comments': total_comments,
        'approved_comments': approved_comments,
        'recent_posts': recent_posts,
        'recent_comments': recent_comments,
    }
    return render(request, 'blog/admin_panel.html', context)

def faq(request):
    """FAQ page"""
    return render(request, 'blog/faq.html')

def legacy_faq(request):
    """Keep old /blog/blog/faq/ bookmarks working."""
    return redirect('blog:faq')
