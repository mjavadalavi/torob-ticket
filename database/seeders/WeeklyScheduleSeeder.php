<?php

namespace Database\Seeders;

use App\Enums\BusType;
use Illuminate\Database\Seeder;
use App\Models\WeeklySchedule;

class WeeklyScheduleSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        $WeeklySchedule = new WeeklySchedule();
        $WeeklySchedule->source_city_id= "esf";
        $WeeklySchedule->destination_city_id= "teh";
        $WeeklySchedule->source_terminal_id= "1";
        $WeeklySchedule->destination_terminal_id= "7";
        $WeeklySchedule->moving_day_number= 3;
        $WeeklySchedule->moving_time_seconds= 28800;
        $WeeklySchedule->traveling_time= 240;
        $WeeklySchedule->capacity= 26;
        $WeeklySchedule->bus_type= BusType::VIP;
        $WeeklySchedule->price= 200000;
        $WeeklySchedule->save();

        $WeeklySchedule1 = new WeeklySchedule();
        $WeeklySchedule1->source_city_id= "esf";
        $WeeklySchedule1->destination_city_id= "ker";
        $WeeklySchedule1->source_terminal_id= "3";
        $WeeklySchedule1->destination_terminal_id= "2";
        $WeeklySchedule1->moving_day_number= 3;
        $WeeklySchedule1->moving_time_seconds= 38800;
        $WeeklySchedule1->traveling_time= 260;
        $WeeklySchedule1->capacity= 26;
        $WeeklySchedule1->bus_type= BusType::VIP;
        $WeeklySchedule1->price= 300000;
        $WeeklySchedule1->save();

        $WeeklySchedule2 = new WeeklySchedule();
        $WeeklySchedule2->source_city_id= "bush";
        $WeeklySchedule2->destination_city_id= "teh";
        $WeeklySchedule2->source_terminal_id= "4";
        $WeeklySchedule2->destination_terminal_id= "7";
        $WeeklySchedule2->moving_day_number= 0;
        $WeeklySchedule2->moving_time_seconds= 29800;
        $WeeklySchedule2->traveling_time= 240;
        $WeeklySchedule2->capacity= 26;
        $WeeklySchedule2->bus_type= BusType::VIP;
        $WeeklySchedule2->price= 205000;
        $WeeklySchedule2->save();
    }
}
