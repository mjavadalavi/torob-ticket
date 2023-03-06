<?php

namespace Database\Seeders;

use App\Enums\BusType;
use App\Models\Chairs;
use Carbon\Carbon;
use Illuminate\Database\Seeder;

class ChairsSeed extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $seed = new Chairs();
        $seed->ws_id = 1;
        $seed->chairs = BusType::VIP_Chair;
        $seed->date = Carbon::now()->addDays(2)->toDateString();
        $seed->save();


        $seed1 = new Chairs();
        $seed1->ws_id = 2;
        $seed1->chairs = BusType::VIP_Chair;
        $seed1->date = Carbon::now()->addDays(3)->toDateString();
        $seed1->save();


        $seed2 = new Chairs();
        $seed2->ws_id = 3;
        $seed2->chairs = BusType::VIP_Chair;
        $seed2->date = Carbon::now()->addWeeks(1)->toDateString();
        $seed2->save();

    }
}
