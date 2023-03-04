<?php

namespace App\Enums;

enum ReservationStatus:int
{
    case Pending = 0;
    case Success = 1;
    case Expired = -1;
    case Cancel = -2;
}
