from __future__ import absolute_import

from six.moves.urllib.parse import urlencode

from datetime import timedelta
from django.core.urlresolvers import reverse
from django.utils import timezone

from sentry.models import OrganizationMemberTeam
from sentry.testutils import (
    APITestCase,
    SnubaTestCase,
)


class OrganizationUserIssuesSearchTest(APITestCase, SnubaTestCase):
    def setUp(self):
        super(OrganizationUserIssuesSearchTest, self).setUp()
        self.org = self.create_organization()
        self.org.flags.allow_joinleave = False
        self.org.save()
        self.team1 = self.create_team(organization=self.org)
        self.team2 = self.create_team(organization=self.org)
        self.project1 = self.create_project(teams=[self.team1])
        self.project2 = self.create_project(teams=[self.team2])
        self.store_event(
            data={
                'fingerprint': ['put-me-in-group1'],
                'environment': self.environment.name,
                'timestamp': (timezone.now() - timedelta(hours=1)).isoformat()[:19],
                'user': {'email': 'foo@example.com'},
            },
            project_id=self.project1.id,
        )
        self.store_event(
            data={
                'fingerprint': ['put-me-in-group1'],
                'environment': self.environment.name,
                'timestamp': (timezone.now() - timedelta(hours=1)).isoformat()[:19],
                'user': {'email': 'bar@example.com'},
            },
            project_id=self.project1.id,
        )
        self.store_event(
            data={
                'fingerprint': ['put-me-in-group1'],
                'environment': self.environment.name,
                'timestamp': (timezone.now() - timedelta(hours=1)).isoformat()[:19],
                'user': {'email': 'foo@example.com'},
            },
            project_id=self.project2.id,
        )

    def get_url(self):
        return reverse('sentry-api-0-organization-issue-search', args=[self.org.slug])

    def test_no_team_access(self):
        user = self.create_user()
        self.create_member(user=user, organization=self.org)
        self.login_as(user=user)

        url = '%s?%s' % (self.get_url(), urlencode({'email': 'foo@example.com'}))

        response = self.client.get(url, format='json')
        assert response.status_code == 200
        assert len(response.data) == 0

    def test_has_access(self):
        user = self.create_user()
        member = self.create_member(user=user, organization=self.org)
        self.login_as(user=user)

        OrganizationMemberTeam.objects.create(
            team=self.team1,
            organizationmember=member,
            is_active=True,
        )

        url = '%s?%s' % (self.get_url(), urlencode({'email': 'foo@example.com'}))
        response = self.client.get(url, format='json')

        # result shouldn't include results from team2/project2 or bar@example.com
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['project']['slug'] == self.project1.slug

        OrganizationMemberTeam.objects.create(
            team=self.team2,
            organizationmember=member,
            is_active=True,
        )

        response = self.client.get(url, format='json')

        # now result should include results from team2/project2
        assert response.status_code == 200
        expected = set([self.project1.slug, self.project2.slug])
        assert set([row['project']['slug'] for row in response.data]) == expected
