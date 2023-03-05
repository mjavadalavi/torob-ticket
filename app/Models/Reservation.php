<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasOne;


class Reservation extends Model
{
    use HasFactory;

    protected $table = 'reservation';

    protected $casts = [
        'chairs' => "array"
    ];

    public function WeeklySchedule(): BelongsTo
    {
        return $this->belongsTo(WeeklySchedule::class);
    }

    /**
     * Get buy for the reservation.
     */
    public function buys(): HasOne
    {
        return $this->hasOne(Buy::class);
    }

    public function chairs(): BelongsTo
    {
        return $this->belongsTo(Chairs::class);
    }

}
