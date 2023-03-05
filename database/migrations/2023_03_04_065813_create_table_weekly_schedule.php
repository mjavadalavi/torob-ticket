<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('weekly_schedule', function (Blueprint $table) {
            $table->id();
            $table->string("source_city_id", 5);
            $table->string("source_terminal_id", 5);
            $table->string("destination_city_id", 5);
            $table->string("destination_terminal_id", 5);
            $table->tinyInteger("moving_day_number");
            $table->integer("moving_time_seconds");
            $table->smallInteger("traveling_time");
            $table->tinyInteger("capacity");
            $table->string("bus_type", 5);
            $table->char("price", 8);
            $table->timestamps();
            $table->softDeletes();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('table__weekly_schedule');
    }
};
