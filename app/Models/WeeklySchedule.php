<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class WeeklySchedule extends Model
{
    use HasFactory;

    protected $casts=[
        'price'=> 'int64'
    ];

    protected $table = 'weekly_schedule';

    /**
     * Get the reservations for the weekly schedule.
     */
    public function Reservations(): HasMany
    {
        return $this->hasMany(Reservation::class);
    }

    /**
     * Get the chairs for the  weekly schedule.
     */
    public function chairs(): HasMany
    {
        return $this->hasMany(Chairs::class)->select(['id', 'chairs']);
    }
}
