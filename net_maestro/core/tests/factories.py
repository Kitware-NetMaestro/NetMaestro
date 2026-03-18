from __future__ import annotations

from django.contrib.auth.models import User
import factory.django

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import EventFile, EventRecord, Run


class UserFactory(factory.django.DjangoModelFactory[User]):
    class Meta:
        model = User

    username = factory.SelfAttribute("email")
    email = factory.Faker("safe_email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")


class RunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Run

    name = factory.Sequence(lambda n: f"TestRun-{n}")
    description = factory.Faker("text", max_nb_chars=200)
    status = RunStatus.RUNNING


class EventFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventFile

    run = factory.SubFactory(RunFactory)
    uploaded = factory.Faker("date_time_this_decade")
    file = factory.django.FileField()


class EventRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventRecord

    event_file = factory.SubFactory(EventFileFactory)
    source_lp = factory.Faker("pyfloat")
    dest_lp = factory.Faker("pyfloat")
    time_step = factory.Faker("pyint")
    event_type = factory.Faker("pyfloat")
    virtual_send = factory.Faker("pyfloat")
    virtual_receive = factory.Faker("pyfloat")
