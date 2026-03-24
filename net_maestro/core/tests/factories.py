from __future__ import annotations

from django.contrib.auth.models import User
import factory.django

from net_maestro.core.constants import RunStatus
from net_maestro.core.models import (
    EventFile,
    EventRecord,
    ModelFile,
    ModelRecord,
    Run,
    SimulationFile,
    SimulationPeRecord,
)


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


class SimulationFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SimulationFile

    run = factory.SubFactory(RunFactory)
    uploaded = factory.Faker("date_time_this_decade")
    file = factory.django.FileField()


class SimulationPeRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SimulationPeRecord

    simulation_file = factory.SubFactory(SimulationFileFactory)
    PE_ID = factory.Sequence(lambda n: n)
    events_processed = factory.Faker("pyint", min_value=0)
    events_aborted = factory.Faker("pyint", min_value=0)
    events_rolled_back = factory.Faker("pyint", min_value=0)
    total_rollbacks = factory.Faker("pyint", min_value=0)
    secondary_rollbacks = factory.Faker("pyint", min_value=0)
    fossil_collection_attempts = factory.Faker("pyint", min_value=0)
    pq_queue_size = factory.Faker("pyint", min_value=0)
    network_sends = factory.Faker("pyint", min_value=0)
    network_reads = factory.Faker("pyint", min_value=0)
    number_gvt = factory.Faker("pyint", min_value=0)
    pe_event_ties = factory.Faker("pyint", min_value=0)
    all_reduce = factory.Faker("pyint", min_value=0)
    efficiency = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    network_read_time = factory.Faker("pyfloat", min_value=0.0)
    network_other_time = factory.Faker("pyfloat", min_value=0.0)
    gvt_time = factory.Faker("pyfloat", min_value=0.0)
    fossil_collect_time = factory.Faker("pyfloat", min_value=0.0)
    event_abort_time = factory.Faker("pyfloat", min_value=0.0)
    event_process_time = factory.Faker("pyfloat", min_value=0.0)
    pq_time = factory.Faker("pyfloat", min_value=0.0)
    rollback_time = factory.Faker("pyfloat", min_value=0.0)
    cancel_q_time = factory.Faker("pyfloat", min_value=0.0)
    avl_time = factory.Faker("pyfloat", min_value=0.0)
    buddy_time = factory.Faker("pyfloat", min_value=0.0)
    lz4_time = factory.Faker("pyfloat", min_value=0.0)
    virtual_time = factory.Faker("pyfloat", min_value=0.0)
    real_time = factory.Faker("pyfloat", min_value=0.0)


class ModelFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ModelFile

    run = factory.SubFactory(RunFactory)
    uploaded = factory.Faker("date_time_this_decade")
    file = factory.django.FileField()


class ModelRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ModelRecord

    model_file = factory.SubFactory(ModelFileFactory)

    lp_id = factory.Faker("pyint", min_value=0)
    component_id = factory.Faker("pyint", min_value=0)
    virtual_time = factory.Faker("pyfloat", min_value=0.0)
    real_time = factory.Faker("pyfloat", min_value=0.0)
    send_count = factory.Faker("pyint", min_value=0)
    send_bytes = factory.Faker("pyint", min_value=0)
    send_time = factory.Faker("pyfloat", min_value=0.0)
    receive_count = factory.Faker("pyint", min_value=0)
    receive_bytes = factory.Faker("pyint", min_value=0)
    receive_time = factory.Faker("pyfloat", min_value=0.0)
