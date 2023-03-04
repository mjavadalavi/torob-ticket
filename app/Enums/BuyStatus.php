<?php

namespace App\Enums;

enum BuyStatus:int
{
    case Pending = 0;
    case Success = 1;
    case Rejected = -1;
    case Extradition = 2;
}
