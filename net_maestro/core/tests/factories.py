from __future__ import annotations

from django.contrib.auth.models import User
import factory.django

from net_maestro.core.constants import ModelType, NodeType, ResultStatus, TrafficType
from net_maestro.core.models import (
    EventFile,
    EventRecord,
    HostNode,
    ModelFile,
    ModelRecord,
    Node,
    NodeLink,
    Result,
    RouterNode,
    Run,
    SimulationFile,
    SimulationPeRecord,
    SwitchNode,
    Topology,
)


class UserFactory(factory.django.DjangoModelFactory[User]):
    class Meta:
        model = User

    username = factory.SelfAttribute("email")
    email = factory.Faker("safe_email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")


class TopologyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Topology

    name = factory.Sequence(lambda n: f"TestTopology-{n}")


class NodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Node

    topology = factory.SubFactory(TopologyFactory)
    model = ModelType.SIMPLEP2P
    name = factory.Sequence(lambda n: f"node-{n}")
    node_type = NodeType.ROUTER
    ingress_bandwidth = factory.Faker("pyfloat", min_value=0.0)
    egress_bandwidth = factory.Faker("pyfloat", min_value=0.0)
    ingress_latency = factory.Faker("pyfloat", min_value=0.0)
    egress_latency = factory.Faker("pyfloat", min_value=0.0)


class HostNodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HostNode

    topology = factory.SubFactory(TopologyFactory)
    model = ModelType.SIMPLEP2P
    name = factory.Sequence(lambda n: f"host-{n}")
    node_type = NodeType.HOST
    ingress_bandwidth = factory.Faker("pyfloat", min_value=0.0)
    egress_bandwidth = factory.Faker("pyfloat", min_value=0.0)
    ingress_latency = factory.Faker("pyfloat", min_value=0.0)
    egress_latency = factory.Faker("pyfloat", min_value=0.0)
    traffic = TrafficType.UNIFORM
    num_messages = factory.Faker("pyint", min_value=0)
    arrival_time = factory.Faker("pyfloat", min_value=0.0)
    payload_size = factory.Faker("pyint", min_value=0)


class RouterNodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = RouterNode

    topology = factory.SubFactory(TopologyFactory)
    model = ModelType.SIMPLEP2P
    name = factory.Sequence(lambda n: f"router-{n}")
    node_type = NodeType.ROUTER
    ingress_bandwidth = factory.Faker("pyfloat", min_value=0.0)
    egress_bandwidth = factory.Faker("pyfloat", min_value=0.0)
    ingress_latency = factory.Faker("pyfloat", min_value=0.0)
    egress_latency = factory.Faker("pyfloat", min_value=0.0)


class SwitchNodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SwitchNode

    topology = factory.SubFactory(TopologyFactory)
    model = ModelType.SIMPLEP2P
    name = factory.Sequence(lambda n: f"switch-{n}")
    node_type = NodeType.SWITCH
    ingress_bandwidth = factory.Faker("pyfloat", min_value=0.0)
    egress_bandwidth = factory.Faker("pyfloat", min_value=0.0)
    ingress_latency = factory.Faker("pyfloat", min_value=0.0)
    egress_latency = factory.Faker("pyfloat", min_value=0.0)


class NodeLinkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NodeLink

    topology = factory.SubFactory(TopologyFactory)
    source = factory.SubFactory(NodeFactory, topology=factory.SelfAttribute("..topology"))
    target = factory.SubFactory(NodeFactory, topology=factory.SelfAttribute("..topology"))


class ResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Result

    status = ResultStatus.RUNNING


class RunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Run

    topology = factory.SubFactory(TopologyFactory)
    result = factory.SubFactory(ResultFactory)
    name = factory.Sequence(lambda n: f"TestRun-{n}")
    description = factory.Faker("text", max_nb_chars=200)


class EventFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EventFile

    result = factory.SubFactory(ResultFactory)
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

    result = factory.SubFactory(ResultFactory)
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

    result = factory.SubFactory(ResultFactory)
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
