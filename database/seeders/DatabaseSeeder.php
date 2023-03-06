<?php

namespace Database\Seeders;

use App\Models\Chairs;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    /**
     * Seed the application's database.
     */
    public function run(): void
    {

        $this->call([
            WeeklyScheduleSeeder::class,
            ChairsSeed::class
        ]);
    }
}
