from app.adapters.alibaba import (
    AlibabaBusAdapter,
    AlibabaFlightAdapter,
    AlibabaTrainAdapter,
)
from app.adapters.booking import BookingFlightAdapter
from app.adapters.flytoday import FlyTodayBusAdapter, FlyTodayFlightAdapter
from app.adapters.mrbilit import (
    MrBilitBusAdapter,
    MrBilitFlightAdapter,
    MrBilitTrainAdapter,
)
from app.adapters.payaneha import PayanehaBusAdapter
from app.adapters.registry import LiveAdapterResources, register_live_adapters
from app.adapters.safar724 import Safar724BusAdapter
from app.adapters.snapptrip import (
    SnappTripBusAdapter,
    SnappTripFlightAdapter,
    SnappTripTrainAdapter,
)

__all__ = [
    "AlibabaBusAdapter",
    "AlibabaFlightAdapter",
    "AlibabaTrainAdapter",
    "BookingFlightAdapter",
    "FlyTodayBusAdapter",
    "FlyTodayFlightAdapter",
    "LiveAdapterResources",
    "MrBilitBusAdapter",
    "MrBilitFlightAdapter",
    "MrBilitTrainAdapter",
    "PayanehaBusAdapter",
    "Safar724BusAdapter",
    "SnappTripBusAdapter",
    "SnappTripFlightAdapter",
    "SnappTripTrainAdapter",
    "register_live_adapters",
]
