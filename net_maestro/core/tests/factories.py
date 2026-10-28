from __future__ import annotations

from django.contrib.auth.models import User
import factory.django

from net_maestro.core.constants import FFWStatsType, RunStatus, SimulationType
from net_maestro.core.models import (
    Ensemble,
    EventFile,
    EventRecord,
    FFWPortRecord,
    FFWResultFile,
    FFWSimulationConfig,
    FFWSwitchRecord,
    FFWTerminalRecord,
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


class EnsembleFactory(factory.django.DjangoModelFactory[Ensemble]):
    class Meta:
        model = Ensemble

    name = factory.Sequence(lambda n: f"TestEnsemble-{n}")
    simulation_type = SimulationType.FFW
    base_params = factory.LazyFunction(
        lambda: {"topology_name": "ffw-fabric-2-site", "traffic": "random", "np": 1, "sync": 1}
    )
    sweep_spec = factory.LazyFunction(lambda: [{"key": "np", "values": [1, 2]}])


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


class FFWSimulationConfigFactory(factory.django.DjangoModelFactory[FFWSimulationConfig]):
    class Meta:
        model = FFWSimulationConfig

    run = factory.SubFactory(RunFactory, simulation_type=SimulationType.FFW)
    topology_name = "ffw-fabric-2-site"


class FFWResultFileFactory(factory.django.DjangoModelFactory[FFWResultFile]):
    class Meta:
        model = FFWResultFile

    run = factory.SubFactory(RunFactory, simulation_type=SimulationType.FFW)
    file = factory.django.FileField(filename="ross-stats-model.bin")


class FFWSwitchRecordFactory(factory.django.DjangoModelFactory[FFWSwitchRecord]):
    """A switch sample with an empty buffer and no traffic; tests set what they check."""

    class Meta:
        model = FFWSwitchRecord

    result_file = factory.SubFactory(FFWResultFileFactory)
    stats_type = FFWStatsType.VT
    ts = 0.0
    peid = 0
    kpid = 0
    lpid = factory.SelfAttribute("switch_id")
    switch_id = 0
    num_ports = 1
    shared_buffer_capacity_mbit = 1000.0
    shared_buffer_occupancy_mbit = 0.0
    sent_mbit = 0.0
    delivered_local_mbit = 0.0
    dropped_mbit = 0.0


class FFWPortRecordFactory(factory.django.DjangoModelFactory[FFWPortRecord]):
    class Meta:
        model = FFWPortRecord

    switch_record = factory.SubFactory(FFWSwitchRecordFactory)
    port_index = 0
    is_terminal = False
    target_index = 1
    port_capacity_mbit_per_interval = 0.0
    port_queued_mbit = 0.0
    port_sent_mbit = 0.0
    port_pause_time_ns = 0.0


class FFWTerminalRecordFactory(factory.django.DjangoModelFactory[FFWTerminalRecord]):
    """A terminal sample with no traffic; tests set what they check."""

    class Meta:
        model = FFWTerminalRecord

    result_file = factory.SubFactory(FFWResultFileFactory)
    stats_type = FFWStatsType.VT
    ts = 0.0
    peid = 0
    kpid = 0
    lpid = factory.SelfAttribute("terminal_id")
    terminal_id = 0
    attached_switch = 0
    generated_mbit = 0.0
    sent_to_switch_mbit = 0.0
    received_mbit = 0.0
    source_backlog_mbit = 0.0
