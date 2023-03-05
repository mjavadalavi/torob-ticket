<?php

use App\Enums\ReservationStatus;
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
        Schema::create('reservation', function (Blueprint $table) {
            $table->id();
            $table->integer('ws_id', false, true);
            $table->integer('chair_id', false, true);
            $table->integer('passenger_count', false, true);
            $table->json('chairs');
            $table->tinyInteger('status')->default(ReservationStatus::Pending->value);
            $table->timestamps();
            $table->foreign('ws_id')
                ->references('id')
                ->on('weekly_schedule')
                ->cascadeOnDelete()
                ->cascadeOnDelete();
            $table->foreign('chair_id')
                ->references('id')
                ->on('chairs')
                ->cascadeOnDelete()
                ->cascadeOnDelete();
            $table->softDeletes();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('reservation');
    }
};
