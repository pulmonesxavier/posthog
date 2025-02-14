from django.test import TestCase, Client
from posthog.models import User, DashboardItem, Action, Person, Event, Team
from social_django.strategy import DjangoStrategy # type: ignore
from social_django.models import DjangoStorage # type: ignore
from social_core.utils import module_member # type: ignore
from posthog.urls import social_create_user

class TestSignup(TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
     
    def test_signup_new_team(self):
        with self.settings(TEST=False):
            response = self.client.post('/setup_admin', {'company_name': 'ACME Inc.', 'name': 'Jane', 'email': 'jane@acme.com', 'password': 'hunter2'}, follow=True)
        self.assertRedirects(response, '/')

        user = User.objects.get() 
        self.assertEqual(user.first_name, 'Jane')
        self.assertEqual(user.email, 'jane@acme.com')

        team = user.team_set.get()
        self.assertEqual(team.name, 'ACME Inc.')
        self.assertEqual(team.users.all()[0], user)

        action = Action.objects.get(team=team)
        self.assertEqual(action.name, 'Pageviews')
        self.assertEqual(action.steps.all()[0].event, '$pageview')

        items = DashboardItem.objects.filter(team=team).order_by('id')
        self.assertEqual(items[0].name, 'Pageviews this week')
        self.assertEqual(items[0].type, 'ActionsLineGraph')
        self.assertEqual(items[0].filters['actions'][0]['id'], action.pk)

        self.assertEqual(items[1].filters['actions'][0]['id'], action.pk)
        self.assertEqual(items[1].type, 'ActionsTable')

class TestSocialSignup(TestCase):
    def setUp(self):
        super().setUp()
        Backend = module_member('social_core.backends.github.GithubOAuth2')
        self.strategy = DjangoStrategy(DjangoStorage)
        self.backend = Backend(self.strategy, redirect_uri='/complete/github')
        self.login_redirect_url = '/'

    def test_custom_create_user_pipeline(self):
        Team.objects.create(signup_token='faketoken')
        details = {'username': 'fake_username', 'email': 'fake@email.com', 'fullname': 'bob bob', 'first_name': 'bob', 'last_name': 'bob'}
        
        # try to create user without a signup token
        result = social_create_user(self.strategy, details, self.backend)
        count = User.objects.count()
        self.assertEqual(count, 0)

        # try to create user without a wrong/unassociated token
        self.strategy.session_set('signup_token', 'wrongtoken')
        result = social_create_user(self.strategy, details, self.backend)
        count = User.objects.count()
        self.assertEqual(count, 0)

        # create user
        self.strategy.session_set('signup_token', 'faketoken')
        result = social_create_user(self.strategy, details, self.backend)
        user = User.objects.get()
        self.assertEqual(result['is_new'], True)
        self.assertEqual(user.email, "fake@email.com")
        