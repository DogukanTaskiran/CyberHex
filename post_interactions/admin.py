from django.contrib import admin
from .models import Like, Dislike, Comment

class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'get_post_id', 'content', 'created_at', 'get_topic_title')
    search_fields = ('author__username', 'content')
    list_filter = ('created_at', 'author')

    def get_post_id(self, obj):
        return obj.post.id if obj.post else None
    get_post_id.short_description = 'Post ID'

    def get_topic_title(self, obj):
        return obj.post.topic.title if obj.post.topic else "No Topic"
    get_topic_title.short_description = 'Topic Title'

admin.site.register(Comment, CommentAdmin)

class BaseReactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_post_id', 'post')

    def get_post_id(self, obj):
        return obj.post.id if obj.post else None
    get_post_id.short_description = 'Post ID'

class LikeAdmin(BaseReactionAdmin):
    pass

class DislikeAdmin(BaseReactionAdmin):
    pass


admin.site.register(Like, LikeAdmin)
admin.site.register(Dislike, DislikeAdmin)