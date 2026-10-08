from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

import logging

logger = logging.getLogger(__name__)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, help_text="Short bio for the author")
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    twitter = models.URLField(blank=True, help_text="Twitter profile URL")
    facebook = models.URLField(blank=True, help_text="Facebook profile URL")
    instagram = models.URLField(blank=True, help_text="Instagram profile URL")
    linkedin = models.URLField(blank=True, help_text="LinkedIn profile URL")
    website = models.URLField(blank=True, help_text="Personal website URL")

    def __str__(self):
        return f"{self.user.username}'s profile"

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('blog:category_detail', args=[self.slug])

class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True, help_text="Short summary for blog list")
    image = models.ImageField(upload_to='blog/', blank=True, null=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    publish_date = models.DateTimeField(default=timezone.now)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated tags")

    class Meta:
        ordering = ['-publish_date']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('blog:detail', args=[self.pk])

    def get_tags_list(self):
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

class Comment(models.Model):
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    author_name = models.CharField(max_length=100)
    author_email = models.EmailField()
    author_website = models.URLField(blank=True)
    content = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    class Meta:
        ordering = ['created_date']

    def __str__(self):
        return f'Comment by {self.author_name} on {self.post.title}'

    def get_replies(self):
        return Comment.objects.filter(parent=self, is_approved=True)

# Signal to create the blog author profile when a User is created.
#
# Previously this was two receivers: one calling a bare UserProfile.create()
# (which raises IntegrityError if a profile already exists) and one that ran
# instance.userprofile.save() on EVERY User.save(), writing the row again even
# when nothing had changed. Because post_save runs inside the caller's
# transaction, a failure here rolled back the whole enclosing operation - for
# example agrolease farmer registration. Now: idempotent, create-only, and
# never allowed to abort the caller.
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        UserProfile.objects.get_or_create(user=instance)
    except Exception:
        # A missing author profile is cosmetic (bio/avatar on blog posts) and is
        # recreated lazily. It must never break user registration.
        logger.exception(
            "Could not create blog UserProfile for user id=%s", instance.pk,
        )
