<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Passenger extends Model
{
    use HasFactory;

    protected $table = 'passenger';

    /**
     * Get the reservations for the weekly schedule.
     */
    public function buys(): HasMany
    {
        return $this->hasMany(Buy::class);
    }
}
