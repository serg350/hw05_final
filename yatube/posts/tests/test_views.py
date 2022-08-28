import shutil
import tempfile
import time
from http import HTTPStatus

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import Post, Group, Comment, Follow

User = get_user_model()

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostPagesTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='testuser')
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        cls.group = Group.objects.create(
            title='Новая группа для тестов',
            slug='test-group',
            description='Тестовое описание'
        )
        cls.post_without_group = Post.objects.create(
            text='Новый текст представленный для примера #2',
            author=cls.user
        )
        time.sleep(0.1)
        cls.post = Post.objects.create(
            text='Новый текст представленный для примера',
            author=cls.user,
            group=cls.group,
            image=uploaded,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='StasBasov')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.post_author = Client()
        self.post_author.force_login(self.post.author)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        cache.clear()
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_posts',
                    kwargs={'slug': self.group.slug}): 'posts/group_list.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse(
                'posts:post_detail',
                kwargs={'post_id': self.post.id}): 'posts/post_detail.html',
            reverse('posts:profile',
                    kwargs={'username': self.user}): 'posts/profile.html',
            reverse('posts:post_edit',
                    kwargs={'post_id': self.post.id}): 'posts/create_post.html'
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.post_author.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_page_show_correct_context(self):
        """Шаблон index сформирован с правильным контекстом."""
        cache.clear()
        response = self.authorized_client.get(reverse('posts:index'))
        first_object = response.context['page_obj'][0]
        self.assertEqual(first_object.group.title, self.post.group.title)
        self.assertEqual(first_object.text, self.post.text)
        self.assertEqual(first_object.author, self.post.author)
        self.assertEqual(first_object.pub_date, self.post.pub_date)
        self.assertEqual(first_object.image, self.post.image)

    def test_group_show_correct_context(self):
        """Шаблон group_posts сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:group_posts', kwargs={'slug': self.group.slug})
        )
        first_object = response.context['page_obj'][0]
        self.assertEqual(first_object.group.title, self.post.group.title)
        self.assertEqual(
            first_object.group.description,
            self.group.description
        )
        self.assertEqual(first_object.group.slug, self.group.slug)
        self.assertEqual(first_object.text, self.post.text)
        self.assertEqual(first_object.image, self.post.image)

    def test_profile_show_correct_context(self):
        """Шаблон profile сформирован с правильным контекстом."""
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': self.post.author})
        )
        self.assertEqual(response.context.get('author'), self.post.author)
        self.assertEqual(response.context['page_obj'][0].image, self.post.image)

    def test_post_detail_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse(
            'posts:post_detail', kwargs={'post_id': self.post.id})
        )
        self.assertEqual(response.context.get('post').text,
                         self.post.text
                         )
        self.assertEqual(response.context.get('post').pub_date,
                         self.post.pub_date
                         )
        self.assertEqual(response.context.get('post').author,
                         self.post.author
                         )
        self.assertEqual(response.context.get('post').group,
                         self.post.group
                         )
        self.assertEqual(response.context.get('post').image,
                         self.post.image
                         )

    def test_post_edit_show_correct_context(self):
        """Шаблон post_edit сформирован с правильным контекстом."""
        response = self.post_author.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id})
        )
        self.assertEqual(response.context.get('post').id, self.post.id)

    def test_post_on_other_list(self):
        """Новый пост с выбранной группой присутствует
         на страницах: index, group_posts, profile"""
        cache.clear()
        templates_list = [
            reverse('posts:index'),
            reverse('posts:group_posts', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': self.post.author})
        ]
        for tmp in templates_list:
            with self.subTest(tmp=tmp):
                response = self.authorized_client.get(tmp)
                self.assertEqual(
                    response.context['page_obj'][0].text, self.post.text
                )

    def test_cache_in_index(self):
        """Шаблон index хранится в кеше"""
        self.post_test_cache = Post.objects.create(
            text='Текст для тестирования кеша',
            author=self.user
        )
        response = self.authorized_client.get(reverse('posts:index'))
        cache_object = response.context['page_obj']
        self.assertEqual(len(cache_object), 3)
        Post.objects.filter(id=self.post_test_cache.id).delete()
        response_cache = self.authorized_client.get(reverse('posts:index'))
        self.assertEqual(response.content, response_cache.content)
        cache.clear()
        response_clear = self.authorized_client.get(reverse('posts:index'))
        self.assertNotEqual(response_cache.content, response_clear.content)


class PostPaginatorTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='testuser')
        cls.user_2 = User.objects.create_user(username='testuser_2')
        cls.group = Group.objects.create(
            title='Новая группа для тестов',
            slug='test-group',
            description='Тестовое описание'
        )
        cls.post = Post.objects.create(
            text='Новый текст представленный для примера',
            author=cls.user,
            group=cls.group
        )
        cls.post_without_group = Post.objects.create(
            text='Новый текст представленный для примера #2',
            author=cls.user
        )
        objs = [
            Post(
                author=cls.user_2,
                text=f'{i}',
                group=cls.group
            )
            for i in range(0, 11)
        ]
        Post.objects.bulk_create(objs=objs)

    def setUp(self):
        self.user = User.objects.create_user(username='StasBasov')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_paginator(self):
        """paginator сформирован правильно."""
        cache.clear()
        paginated_urls = {
            reverse('posts:index'): 10,
            reverse('posts:index') + '?page=2': 3,
            reverse('posts:group_posts',
                    kwargs={'slug': self.group.slug}): 10,
            reverse('posts:group_posts',
                    kwargs={'slug': self.group.slug}
                    ) + '?page=2': 2,
            reverse('posts:profile',
                    kwargs={'username': 'testuser_2'}
                    ): 10,
            reverse('posts:profile',
                    kwargs={'username': 'testuser_2'}
                    ) + '?page=2': 1
        }

        for name, pages in paginated_urls.items():
            with self.subTest(name=name):
                response = self.authorized_client.get(name)
                self.assertEqual(len(response.context['page_obj']), pages)


class CommentTestViews(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='testuser')
        cls.group = Group.objects.create(
            title='Новая группа для тестов',
            slug='test-group',
            description='Тестовое описание'
        )
        cls.post = Post.objects.create(
            text='Новый текст представленный для примера',
            author=cls.user,
            group=cls.group
        )
        cls.comments = Comment.objects.create(
            post=cls.post,
            author=cls.user,
            text='Тестовый комментарий'
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_add_comment_for_authorized_client(self):
        """Комментировать может только авторизованный пользователь"""
        response = self.authorized_client.get(
            reverse(
                'posts:add_comment',
                kwargs={
                    'post_id': self.post.id
                }
            )
        )
        self.assertEqual(
            response.status_code,
            HTTPStatus.FOUND,
            ('Неавторизированный пользователь'
             ' не может оставлять комментарий')
        )
        self.assertRedirects(
            response,
            reverse(
                'posts:post_detail',
                kwargs={'post_id': self.post.id}
            )
        )

    def test_comment_view_on_post_detail(self):
        """Комментрий отображается на странице  post_detail"""
        responce = self.guest_client.get(
            reverse(
                'posts:post_detail',
                kwargs={'post_id': self.post.id}
            )
        )
        self.assertEqual(
            responce.context.get('comments')[0].text,
            self.comments.text
        )


class FollowViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='testuser')
        cls.user_no_follow = User.objects.create_user(username='no_follow')
        cls.follower = User.objects.create_user(username='test')
        cls.group = Group.objects.create(
            title='Новая группа для тестов',
            slug='test-group',
            description='Тестовое описание'
        )
        cls.post_no_follower = Post.objects.create(
            text='Новый текст представленный для примера',
            author=cls.user_no_follow,
            group=cls.group
        )
        time.sleep(0.1)
        cls.post = Post.objects.create(
            text='Новый текст представленный для примера',
            author=cls.user,
            group=cls.group
        )

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.follower)

    def test_follow(self):
        """Тест работы подписки на автора"""
        cache.clear()
        response = self.authorized_client.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': self.user}
            )
        )
        follower = Follow.objects.filter(
            user=self.follower,
            author=self.user,
        ).exists()
        self.assertTrue(
            follower,
            'Не работает подписка на автора'
        )

    def test_unfollow(self):
        """Тест работы удаления подписки на автора"""
        self.authorized_client.get(
            reverse(
                'posts:profile_unfollow',
                kwargs={'username': self.user}
            )
        )
        follower = Follow.objects.filter(
            user=self.follower,
            author=self.user,
        ).delete()
        self.assertTrue(
            follower,
            'Не работает удаление подписки на автора'
        )

    def test_follow_index_works_correctly(self):
        """Новая запись пользователя появляется в ленте тех,
        кто на него подписан"""
        self.authorized_client.get(
            reverse(
                'posts:profile_follow',
                kwargs={'username': self.user}
            )
        )
        response = self.authorized_client.get(
            reverse(
                'posts:follow_index'
            )
        )
        self.assertEqual(
            response.context.get('page_obj')[0].text,
            self.post.text
        )

