from anthill.framework.utils.urls import reverse, build_absolute_uri
from anthill.platform.services import PlainService


class Service(PlainService):
    """Anthill default service."""

    async def set_messenger_url(self):
        path = reverse('messenger')
        host_url = self.app.registry_entry['external']
        url = build_absolute_uri(host_url, path)
        self.settings.update(messenger_url=url)
