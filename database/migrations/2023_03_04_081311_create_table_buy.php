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
        Schema::create('buy', function (Blueprint $table) {
            $table->id();
            $table->integer('reservation_id', false,true);
            $table->bigInteger('passenger_id', false, true);
            $table->boolean('status')->default(false);
            $table->timestamps();
            $table->foreign('reservation_id')
                ->references('id')
                ->on('reservation')
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
        Schema::dropIfExists('buy');
    }
};
